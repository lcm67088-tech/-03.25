"""
AuditLog 라우터
GET /api/v1/audit  — 감사 로그 조회 (ADMIN)

DB 실제 컬럼: entity_type, entity_id, field_name, before_value, after_value, extra_data
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.response import paginated
from app.models.import_job import AuditLog
from app.models.user import User

router = APIRouter()


@router.get("", summary="감사 로그 조회 (ADMIN)")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    actor_id: Optional[uuid.UUID] = Query(None),
    entity_type: Optional[str] = Query(None, description="예: Order, OrderItem, Place"),
    entity_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = select(AuditLog)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    if action:
        q = q.where(AuditLog.action == action)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            q.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()

    return paginated(
        [
            {
                "id": str(lg.id),
                "actor_id": str(lg.actor_id) if lg.actor_id else None,
                "actor_role": lg.actor_role,
                "entity_type": lg.entity_type,
                "entity_id": str(lg.entity_id) if lg.entity_id else None,
                "action": lg.action,
                "field_name": lg.field_name,
                "before_value": lg.before_value,
                "after_value": lg.after_value,
                "extra_data": lg.extra_data,
                "created_at": lg.created_at.isoformat(),
            }
            for lg in rows
        ],
        total, page, page_size,
    )
