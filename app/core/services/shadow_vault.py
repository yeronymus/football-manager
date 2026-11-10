import json
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.audit import record_audit_log
from app.core.services.saas import decrypt_secret_envelope, encrypt_secret_envelope
from app.db.models import ChatMember, Position, ShadowIdentityVault, User


async def archive_and_anonymize_user(
    session: AsyncSession,
    user_id: int,
    actor_user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    reason: str = "gdpr_erasure",
) -> Dict[str, Any]:
    """
    Two-tier GDPR & Archival Identity Vault workflow:
    1. Captures the user's complete identity and historical metadata into an encrypted
       `ShadowIdentityVault` record (cold vault).
    2. Anonymizes the public `User` and `ChatMember` records in the hot production schema
       (`Former Participant #ID`) without deleting foreign-key references in `Signup`,
       `GameStats`, or `RatingHistory`.
    """
    user = await session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    if getattr(user, "is_anonymized", False):
        return {
            "status": "already_anonymized",
            "user_id": user_id,
            "anonymized_alias": user.full_name,
        }

    pos_val = (
        user.player_position.value
        if hasattr(user.player_position, "value")
        else str(user.player_position or "CM")
    )
    snapshot = {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "username": user.username,
        "player_position": pos_val,
        "alt_positions": list(user.alt_positions or []),
        "rating": user.rating,
        "games_played": user.games_played,
        "stats_matches": user.stats_matches,
        "stats_mvp": user.stats_mvp,
        "has_multisport_card": bool(getattr(user, "has_multisport_card", False)),
    }

    encrypted_blob = encrypt_secret_envelope(json.dumps(snapshot, ensure_ascii=False))
    alias = f"Former Participant #{abs(int(user_id)) % 100000:05d}"

    vault_entry = ShadowIdentityVault(
        original_user_id=user_id,
        organization_id=organization_id,
        chat_id=chat_id,
        encrypted_payload=encrypted_blob,
        anonymized_alias=alias,
        archived_reason=reason,
        archived_by_user_id=actor_user_id,
    )
    session.add(vault_entry)

    # Anonymize hot User record while keeping all historical relational integrity intact
    user.full_name = alias
    user.username = None
    user.is_anonymized = True

    # Anonymize any ChatMember rows for this user
    cm_stmt = select(ChatMember).where(ChatMember.user_id == user_id)
    if chat_id is not None:
        cm_stmt = cm_stmt.where(ChatMember.chat_id == chat_id)
    cm_rows = (await session.execute(cm_stmt)).scalars().all()
    for cm in cm_rows:
        cm.full_name = alias
        cm.username = None

    record_audit_log(
        session,
        action="USER_ARCHIVED_TO_SHADOW_VAULT",
        actor_user_id=actor_user_id,
        chat_id=chat_id,
        target_type="user",
        target_id=user_id,
        payload={"anonymized_alias": alias, "reason": reason},
    )

    await session.flush()
    return {
        "status": "anonymized",
        "user_id": user_id,
        "anonymized_alias": alias,
        "vault_id": vault_entry.id,
    }


async def restore_user_from_vault(
    session: AsyncSession,
    user_id: int,
    actor_user_id: Optional[int] = None,
    chat_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Restores a previously anonymized user's real identity from the latest encrypted
    `ShadowIdentityVault` snapshot.
    """
    stmt = (
        select(ShadowIdentityVault)
        .where(ShadowIdentityVault.original_user_id == user_id)
        .order_by(ShadowIdentityVault.id.desc())
        .limit(1)
    )
    vault_entry = (await session.execute(stmt)).scalar_one_or_none()
    if not vault_entry:
        raise ValueError(f"No ShadowIdentityVault snapshot found for user {user_id}")

    decrypted_json = decrypt_secret_envelope(vault_entry.encrypted_payload)
    snapshot = json.loads(decrypted_json)

    user = await session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    user.full_name = snapshot.get("full_name") or user.full_name
    user.username = snapshot.get("username")
    pos_str = snapshot.get("player_position", "CM")
    if pos_str in Position.__members__:
        user.player_position = Position[pos_str]
    user.alt_positions = snapshot.get("alt_positions", [])
    user.has_multisport_card = bool(snapshot.get("has_multisport_card", False))
    user.is_anonymized = False

    cm_rows = (
        await session.execute(select(ChatMember).where(ChatMember.user_id == user_id))
    ).scalars().all()
    for cm in cm_rows:
        cm.full_name = user.full_name
        cm.username = user.username

    record_audit_log(
        session,
        action="USER_RESTORED_FROM_SHADOW_VAULT",
        actor_user_id=actor_user_id,
        chat_id=chat_id,
        target_type="user",
        target_id=user_id,
        payload={"restored_name": user.full_name},
    )

    await session.flush()
    return {
        "status": "restored",
        "user_id": user_id,
        "full_name": user.full_name,
        "username": user.username,
    }
