"""
AuditLog 라우터
GET /api/v1/audit  — 감사 로그 조회 (ADMIN)
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
    target_type: Optional[str] = Query(None),
    target_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = select(AuditLog)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if target_type:
        q = q.where(AuditLog.target_type == target_type)
    if target_id:
        q = q.where(AuditLog.target_id == target_id)
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
                "target_type": lg.target_type,
                "target_id": str(lg.target_id) if lg.target_id else None,
                "action": lg.action,
                "before_data": lg.before_data,
                "after_data": lg.after_data,
                "detail": lg.detail,
                "ip_address": lg.ip_address,
                "created_at": lg.created_at.isoformat(),
            }
            for lg in rows
        ],
        total, page, page_size,
    )
