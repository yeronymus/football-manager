import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.db.models import Game, GameStatus, Signup, SignupStatus, User
from app.scheduler.tasks import send_pre_game_reminder_task
from app.infrastructure.scheduler.service import SchedulerService


@pytest.mark.asyncio
async def test_send_pre_game_reminder_task_formats_mentions_and_respect_note():
    match_dt = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
    game = Game(id=77, chat_id=-1001, status=GameStatus.OPEN, date_time=match_dt, location="Strahov Field 3")
    user1 = User(user_id=111, full_name="Adil", username="baizhanov9")
    signup1 = Signup(id=1, game_id=77, user_id=111, status=SignupStatus.ACTIVE)

    user2 = User(user_id=222, full_name="Almas", username=None)
    signup2 = Signup(id=2, game_id=77, user_id=222, status=SignupStatus.ACTIVE)

    session = AsyncMock()
    session.get.return_value = game

    # Mock execute for active signups
    exec_mock = MagicMock()
    exec_mock.all.return_value = [(signup1, user1), (signup2, user2)]
    session.execute.return_value = exec_mock

    with patch("app.scheduler.tasks.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__.return_value = session
        with patch("app.scheduler.tasks.bot.send_message", new=AsyncMock()) as mock_send:
            with patch("app.bot.utils.resolve_chat_language", new=AsyncMock(return_value="ru")):
                await send_pre_game_reminder_task(game_id=77)

                assert mock_send.called
                call_kwargs = mock_send.call_args.kwargs
                assert call_kwargs["chat_id"] == -1001
                sent_text = call_kwargs["text"]

                # Verifications:
                # 1. Mention of players
                assert "@baizhanov9" in sent_text
                assert "Almas" in sent_text
                # 2. Warm-up time (20 minutes before 20:00)
                assert "20 минут" in sent_text
                # 3. User requested respectful phrase: "Уважайте своё и чужое время."
                assert "Уважайте своё и чужое время" in sent_text


def test_scheduler_service_schedules_pre_game_reminder():
    service = SchedulerService()
    now_utc = datetime.now(timezone.utc)
    # Match in 5 hours -> T-3h run date is in 2 hours (> now)
    match_dt = now_utc + timedelta(hours=5)

    with patch("app.infrastructure.scheduler.service.scheduler.add_job") as mock_add:
        service.schedule_pre_game_reminder(game_id=88, date_time=match_dt)
        assert mock_add.called
        kwargs = mock_add.call_args.kwargs
        assert kwargs["id"] == "reminder_t3h_88"


def test_scheduler_service_cancels_pre_game_reminder():
    service = SchedulerService()
    with patch("app.infrastructure.scheduler.service.scheduler.get_job") as mock_get:
        mock_job = MagicMock()
        mock_get.return_value = mock_job
        with patch("app.infrastructure.scheduler.service.scheduler.remove_job") as mock_remove:
            service.cancel_game_tasks(game_id=88)
            # Should have removed voting, gk_release, publish, mvp_calc, AND reminder_t3h
            removed_ids = [call.args[0] for call in mock_remove.call_args_list]
            assert "reminder_t3h_88" in removed_ids
