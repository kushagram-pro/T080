import logging

from sqlalchemy.orm import Session

from app.models import AuditAction, AuditLog, User

logger = logging.getLogger("audit")


def record(db: Session, actor: User, action: AuditAction, target: User | None = None, details: str | None = None) -> None:
    """Add an audit entry to the current transaction.

    It is committed together with the action it describes, so a rolled-back
    action never leaves a misleading audit row behind.
    """
    db.add(AuditLog(actor_id=actor.id, action=action, target_user_id=target.id if target else None, details=details))
    logger.info(
        "actor=%s action=%s target=%s details=%s",
        actor.id, action.value, target.id if target else None, details,
    )
