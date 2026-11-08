import inspect
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog

logger = logging.getLogger(__name__)


def record_audit_log(
    session: Optional[AsyncSession],
    *,
    action: str,
    actor_user_id: Optional[int],
    chat_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Creates and stages an immutable AuditLog entry on the provided SQLAlchemy session.
    """
    entry = AuditLog(
        chat_id=chat_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        payload=dict(payload or {}),
    )
    add_fn = getattr(session, "add", None) if session is not None else None
    if add_fn is not None and not inspect.iscoroutinefunction(add_fn):
        try:
            add_fn(entry)
        except Exception as e:
            logger.warning(f"Failed to stage audit log entry for action={action}: {e}")
    return entry
