import re
from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game, GameStatus

_URL_PATTERN = re.compile(r"\(?https?://[^\s)]+\)?")


def clean_location(loc: Optional[str]) -> Optional[str]:
    """Strips embedded HTTP/HTTPS links from a location string cleanly."""
    if not loc:
        return loc
    return _URL_PATTERN.sub("", loc).strip()


def resolve_tenant_chat_id_variants(
    chat_id: int, channel_id: Optional[int] = None
) -> set[int]:
    """Returns canonical and legacy Telegram supergroup/channel ID variants for a tenant."""
    chat_id_str = str(chat_id)
    alt_chat_id = (
        int(chat_id_str.replace("-100", "-"))
        if "-100" in chat_id_str
        else int("-100" + chat_id_str.replace("-", ""))
    )
    variants = {chat_id, alt_chat_id, abs(chat_id), abs(alt_chat_id)}

    if channel_id:
        chan_str = str(channel_id)
        alt_chan = (
            int(chan_str.replace("-100", "-"))
            if "-100" in chan_str
            else int("-100" + chan_str.replace("-", ""))
        )
        variants.update([channel_id, alt_chan, abs(channel_id), abs(alt_chan)])

    return variants


async def get_group_game_number(session: AsyncSession, game: Game) -> int:
    """
    Returns 1-based sequential game number within its chat group.
    Uses O(1) persisted `game.sequence_number` when available, falling back to SQL count.
    """
    if not game:
        return 1
    seq = getattr(game, "sequence_number", None)
    if isinstance(seq, int) and seq > 0:
        return seq
    if not getattr(game, "chat_id", None):
        return 1

    try:
        chat_ids = resolve_tenant_chat_id_variants(
            game.chat_id, getattr(game, "channel_id", None)
        )
        chat_cond = Game.chat_id.in_(chat_ids)
        if hasattr(Game, "channel_id"):
            chat_cond = or_(chat_cond, Game.channel_id.in_(chat_ids))

        status_cond = or_(Game.status != GameStatus.CANCELLED, Game.id == game.id)
        res = await session.execute(
            select(func.count(Game.id)).where(
                chat_cond,
                status_cond,
                Game.id <= game.id,
            )
        )
        val = res.scalar()
        if isinstance(val, int) and val > 0:
            return val
        return 1
    except Exception:
        return 1


async def compute_next_game_sequence_number(
    session: AsyncSession, chat_id: int, channel_id: Optional[int] = None
) -> int:
    """Computes the next 1-based sequence_number for a newly created game in a tenant group."""
    try:
        chat_ids = resolve_tenant_chat_id_variants(chat_id, channel_id)
        chat_cond = Game.chat_id.in_(chat_ids)
        if hasattr(Game, "channel_id"):
            chat_cond = or_(chat_cond, Game.channel_id.in_(chat_ids))

        res = await session.execute(
            select(func.count(Game.id)).where(
                chat_cond,
                Game.status != GameStatus.CANCELLED,
            )
        )
        cnt = res.scalar()
        if isinstance(cnt, int) and cnt >= 0:
            return cnt + 1
    except Exception:
        pass
    return 1


async def get_group_game_numbers_batch(
    session: AsyncSession, games: Sequence[Game]
) -> dict[int, int]:
    """Resolves game sequence numbers for a collection of games, avoiding N+1 when sequence_number is set."""
    result: dict[int, int] = {}
    for g in games:
        if not g or getattr(g, "id", None) is None:
            continue
        seq = getattr(g, "sequence_number", None)
        if isinstance(seq, int) and seq > 0:
            result[g.id] = seq
        else:
            result[g.id] = await get_group_game_number(session, g)
    return result
