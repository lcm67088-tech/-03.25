"""
모든 모델 임포트 — Alembic autogenerate 감지용
임포트 순서: 의존성 없는 것부터 (순환 임포트 방지)
"""
# Base (SQLAlchemy metadata root)
from app.core.database import Base  # noqa: F401
from app.models.base import BaseModel, ImmutableBase  # noqa: F401

# 독립 엔티티
from app.models.user import User  # noqa: F401
from app.models.agency import Agency, Brand  # noqa: F401
from app.models.provider import (  # noqa: F401
    Provider,
    StandardProductType,
    SellableOffering,
    ProviderOffering,
    SellableProviderMapping,
)

# Place 도메인 (users, agencies, brands 의존)
from app.models.place import Place, PlaceRawSnapshot, PlaceReviewLog  # noqa: F401

# Order 도메인 (users, agencies, brands, places, provider 의존)
from app.models.order import (  # noqa: F401
    OrderRawInput,
    Order,
    OrderItem,
    OrderItemStatusHistory,
)

# 인프라
from app.models.import_job import ImportJob, AuditLog  # noqa: F401

__all__ = [
    "Base",
    "BaseModel",
    "ImmutableBase",
    "User",
    "Agency",
    "Brand",
    "Provider",
    "StandardProductType",
    "SellableOffering",
    "ProviderOffering",
    "SellableProviderMapping",
    "Place",
    "PlaceRawSnapshot",
    "PlaceReviewLog",
    "OrderRawInput",
    "Order",
    "OrderItem",
    "OrderItemStatusHistory",
    "ImportJob",
    "AuditLog",
]
