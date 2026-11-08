"""
Flash-Crowd Concurrency, Matchmaking Optimization & Telegram Coalescing Benchmark Suite.

Simulates:
1. 100 concurrent players competing for 16 active match slots under serialized row-level locking
   (`SELECT ... FOR UPDATE` mutex simulation) -> verifies zero overbooking (16 ACTIVE, 84 RESERVE)
   and measures p50 / p95 / p99 slot-allocation latency.
2. N-Team RoleBasedBalancingStrategy + 2-opt local-search variance reduction across 100 synthetic
   rosters (2-team and 3-team configurations).
3. TelegramRenderDebouncer coalescing efficiency under a 100-event flash-crowd burst.
"""

import asyncio
from datetime import datetime, timedelta
import os
import statistics
import sys
import time
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.bot.listeners import TelegramRenderDebouncer
from app.core.domain.balancer import (
    Player,
    RoleBasedBalancingStrategy,
    _team_spread_sq,
)
from app.core.services.roster import RosterService
from app.db.models import Game, GameStatus, Position, Signup, SignupStatus, User


class InMemoryLockedGameRepo:
    """Simulates PostgreSQL `SELECT ... FOR UPDATE` row-level serialization for a single Game row."""

    def __init__(self, game: Game):
        self.game = game
        self.lock = asyncio.Lock()
        self.signups: list[Signup] = []

    async def get_with_lock(self, game_id: int) -> Game:
        await self.lock.acquire()
        return self.game

    async def get_signup(self, game_id: int, user_id: int):
        for s in self.signups:
            if s.user_id == user_id:
                return s
        return None

    async def get_active_signups_count(self, game_id: int) -> int:
        return sum(1 for s in self.signups if s.status == SignupStatus.ACTIVE)

    async def get_active_gk_count(self, game_id: int) -> int:
        return 0

    def create_signup(self, game_id: int, user_id: int, status: SignupStatus) -> Signup:
        s = Signup(
            id=len(self.signups) + 1,
            game_id=game_id,
            user_id=user_id,
            status=status,
        )
        self.signups.append(s)
        return s


class SimulatedLockUoW:
    def __init__(self, repo: InMemoryLockedGameRepo):
        self.game_repo = repo
        self.user_repo = AsyncMock()
        self.user_repo.get_active_card = AsyncMock(return_value=None)

    def defer_cache_eviction(self, key: str) -> None:
        pass

    async def release(self):
        if self.game_repo.lock.locked():
            self.game_repo.lock.release()


async def benchmark_flash_crowd_signups(total_requests: int = 100, max_players: int = 16) -> dict:
    game = Game(
        id=1,
        chat_id=-100100,
        max_players=max_players,
        status=GameStatus.OPEN,
        date_time=datetime.now() + timedelta(days=2),
        created_at=datetime.now() - timedelta(hours=1),
        registration_hours=0,
    )
    shared_repo = InMemoryLockedGameRepo(game)
    latencies_ms: list[float] = []

    async def _worker(uid: int):
        uow = SimulatedLockUoW(shared_repo)
        service = RosterService(uow)
        user = User(
            user_id=uid,
            full_name=f"Player {uid}",
            player_position=Position.CM,
            rating=100 + (uid % 50),
        )
        t0 = time.perf_counter()
        try:
            res = await service.join_player(game_id=1, user=user)
            return res
        finally:
            await uow.release()
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    t_start = time.perf_counter()
    with patch("app.core.services.cache.cache_service.evict", new_callable=AsyncMock):
        results = await asyncio.gather(*[_worker(1000 + i) for i in range(total_requests)])
    wall_ms = (time.perf_counter() - t_start) * 1000.0

    active_count = sum(1 for s in shared_repo.signups if s.status == SignupStatus.ACTIVE)
    reserve_count = sum(1 for s in shared_repo.signups if s.status == SignupStatus.RESERVE)
    sorted_lat = sorted(latencies_ms)
    p50 = sorted_lat[int(0.50 * len(sorted_lat))]
    p95 = sorted_lat[int(0.95 * len(sorted_lat))]
    p99 = sorted_lat[int(0.99 * len(sorted_lat))]

    assert active_count == max_players, f"Expected {max_players} ACTIVE, got {active_count}"
    assert reserve_count == total_requests - max_players
    assert all(r.success for r in results)

    return {
        "total_requests": total_requests,
        "active_count": active_count,
        "reserve_count": reserve_count,
        "wall_ms": round(wall_ms, 2),
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "p99_ms": round(p99, 3),
    }


def benchmark_balancer_2opt(iterations: int = 100) -> dict:
    strategy = RoleBasedBalancingStrategy()
    positions = [
        "GK", "GK", "GK",
        "CB", "CB", "LB", "RB", "DEF", "CB",
        "CM", "CM", "CAM", "CDM", "LM", "RM",
        "ST", "LW", "RW",
    ]
    durations_ms: list[float] = []
    spreads: list[float] = []

    for seed in range(iterations):
        players = [
            Player(
                user_id=i + 1,
                full_name=f"P{i + 1}",
                position=positions[i % len(positions)],
                rating_override=80 + ((i * 19 + seed * 13) % 140),
            )
            for i in range(18)
        ]
        t0 = time.perf_counter()
        teams = strategy.balance(players, team_count=3)
        durations_ms.append((time.perf_counter() - t0) * 1000.0)
        spreads.append(_team_spread_sq(teams))

    return {
        "iterations": iterations,
        "mean_ms": round(statistics.mean(durations_ms), 3),
        "p95_ms": round(sorted(durations_ms)[int(0.95 * len(durations_ms))], 3),
        "mean_spread_sq": round(statistics.mean(spreads), 2),
    }


async def benchmark_debouncer_coalescing(burst_size: int = 100) -> dict:
    calls = 0

    async def fake_edit(game_id: int):
        nonlocal calls
        calls += 1

    debouncer = TelegramRenderDebouncer(fake_edit, cooldown_seconds=0.05)
    for _ in range(burst_size):
        await debouncer.trigger(1)
    await asyncio.sleep(0.08)

    return {
        "burst_events": burst_size,
        "executed_telegram_edits": calls,
        "coalesced_drops": debouncer.coalesced_drops,
        "reduction_pct": round((1.0 - (calls / burst_size)) * 100.0, 1),
    }


async def main():
    fc = await benchmark_flash_crowd_signups(100, 16)
    bal = benchmark_balancer_2opt(100)
    deb = await benchmark_debouncer_coalescing(100)

    print("=== FLASH-CROWD CONCURRENCY (100 concurrent signups -> 16 slots) ===")
    print(fc)
    print("=== 3-TEAM 2-OPT BALANCER (100 rosters x 18 players) ===")
    print(bal)
    print("=== TELEGRAM RENDER DEBOUNCER (100 rapid events) ===")
    print(deb)


if __name__ == "__main__":
    asyncio.run(main())
