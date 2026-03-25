"""
모든 모델의 공통 Base 믹스인
UUID PK + timezone-aware 타임스탬프
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimestampMixin:
    """created_at / updated_at 공통 컬럼"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """UUID PK 공통 컬럼"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )


class BaseModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    일반 엔티티용 Base (UUID PK + 타임스탬프)
    """
    __abstract__ = True


class ImmutableBase(UUIDPrimaryKeyMixin, Base):
    """
    원본 불변 테이블용 Base (UUID PK + created_at만)
    UPDATE/DELETE 금지 원칙 적용 대상
    - place_raw_snapshots
    - order_raw_inputs
    - place_review_logs
    - order_item_status_histories
    - audit_logs
    """
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
