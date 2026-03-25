"""AuditLog 기록 서비스 (공통 유틸)

DB 실제 컬럼 (001_initial_schema.py 기준):
  id, actor_id, actor_role, entity_type, entity_id,
  action, field_name, before_value, after_value, extra_data, created_at
"""
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import AuditLog
from app.models.user import User


async def record_audit(
    db: AsyncSession,
    actor: Optional[User],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    field_name: Optional[str] = None,
    before_value: Optional[str] = None,
    after_value: Optional[str] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> AuditLog:
    """
    AuditLog를 INSERT하고 반환.
    commit()은 호출자가 책임.
    단독 commit이 필요한 경우 이 함수 호출 후 db.commit() 수행.
    """
    log = AuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
        before_value=before_value,
        after_value=after_value,
        extra_data=extra_data,
    )
    db.add(log)
    await db.flush()
    return log
