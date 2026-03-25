"""AuditLog 기록 서비스 (공통 유틸)"""
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import AuditLog
from app.models.user import User


async def record_audit(
    db: AsyncSession,
    actor: Optional[User],
    action: str,
    domain: str,
    target_id: Optional[uuid.UUID] = None,
    target_type: Optional[str] = None,
    before_snapshot: Optional[dict[str, Any]] = None,
    after_snapshot: Optional[dict[str, Any]] = None,
    detail: Optional[str] = None,
    request_id: Optional[str] = None,
) -> AuditLog:
    """
    AuditLog를 INSERT하고 반환.
    commit()은 호출자가 책임.
    단독 commit이 필요한 경우 이 함수 호출 후 db.commit() 수행.
    """
    log = AuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        actor_email_snapshot=actor.email if actor else None,
        action=action,
        domain=domain,
        target_id=target_id,
        target_type=target_type or domain,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        detail=detail,
        request_id=request_id,
    )
    db.add(log)
    # flush — 같은 트랜잭션에 포함, commit은 호출자가 담당
    await db.flush()
    return log
