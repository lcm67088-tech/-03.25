"""
Provider / StandardProductType / Offering / Mapping 모델
판매 구조(SellableOffering)와 실행 구조(ProviderOffering) 분리 원칙 적용
"""
import uuid
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    pass


class Provider(BaseModel):
    """
    실행처 (매체사 등)
    취합 시트의 '매체사' 컬럼에 대응 (피크, NNW, ...)
    """
    __tablename__ = "providers"
    __table_args__ = {"comment": "실행처 (매체사 등). 취합 시트 매체사 컬럼 대응."}

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="실행처명"
    )
    provider_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="media_company | individual | internal [가정: 분류 체계 미확정]",
    )
    contact_info: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment='{"email": "...", "phone": "...", "slack_channel": "..."}',
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    provider_offerings: Mapped[list["ProviderOffering"]] = relationship(
        "ProviderOffering", back_populates="provider", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Provider {self.name}>"


class StandardProductType(BaseModel):
    """
    표준 상품 유형
    [초안/제안안] 취합 데이터 기반 제안. 확정본 아님.
    코드: TRAFFIC | SAVE | AI_REAL | AI_NONREAL | BLOG_REPORTER | BLOG_DISPATCH |
          XIAOHONGSHU | DIANPING
    """
    __tablename__ = "standard_product_types"
    __table_args__ = {
        "comment": "[초안/제안안] 표준 상품 유형. 취합 데이터 기반 제안. 확정본 아님."
    }

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="TRAFFIC | SAVE | AI_REAL | AI_NONREAL | BLOG_REPORTER | BLOG_DISPATCH | XIAOHONGSHU | DIANPING",
    )
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="표시명"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="naver_place | blog | xiaohongshu | dianping [가정: 미확정]",
    )
    requires_period: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="기간형(시작일~종료일) 여부",
    )
    requires_daily_qty: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="일 수량 필드 필요 여부",
    )
    supports_subtype: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="내부 세부 구분(product_subtype) 필요 여부. BLOG_DISPATCH에 해당.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Relations
    sellable_offerings: Mapped[list["SellableOffering"]] = relationship(
        "SellableOffering", back_populates="standard_product_type", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<StandardProductType {self.code}>"


class SellableOffering(BaseModel):
    """
    고객 판매 상품 (판매 구조 축)
    ProviderOffering(실행 구조 축)과 반드시 분리.
    1 SellableOffering : N ProviderOffering 연결 가능.
    """
    __tablename__ = "sellable_offerings"
    __table_args__ = {"comment": "고객 판매 상품. 판매 구조 축 (실행 구조와 분리)."}

    standard_product_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("standard_product_types.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False, comment="판매 상품명")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_price: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="기준 단가 (nullable, 미확정)"
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="건 | 일 | 회"
    )
    spec_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="스펙 프리셋 (유연)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    standard_product_type: Mapped["StandardProductType"] = relationship(
        "StandardProductType", back_populates="sellable_offerings"
    )
    provider_mappings: Mapped[list["SellableProviderMapping"]] = relationship(
        "SellableProviderMapping", back_populates="sellable_offering", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<SellableOffering {self.name}>"


class ProviderOffering(BaseModel):
    """
    실행처 실행 상품 (실행 구조 축)
    SellableOffering(판매 구조 축)과 반드시 분리.
    """
    __tablename__ = "provider_offerings"
    __table_args__ = {"comment": "실행처 실행 상품. 실행 구조 축 (판매 구조와 분리)."}

    standard_product_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("standard_product_types.id"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False, comment="실행 상품명 (내부명)")
    cost_price: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="실행처 원가 (nullable, 미확정)"
    )
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    spec_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    provider: Mapped["Provider"] = relationship(
        "Provider", back_populates="provider_offerings"
    )
    sellable_mappings: Mapped[list["SellableProviderMapping"]] = relationship(
        "SellableProviderMapping", back_populates="provider_offering", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<ProviderOffering {self.name} @ {self.provider_id}>"


class SellableProviderMapping(BaseModel):
    """
    SellableOffering ↔ ProviderOffering 연결 (1:N)
    하나의 판매 상품에 여러 실행처가 연결 가능.
    [가정] routing_conditions 정책 미확정 → JSONB 유연 시작
    """
    __tablename__ = "sellable_provider_mappings"
    __table_args__ = (
        UniqueConstraint("sellable_offering_id", "provider_offering_id", name="uq_sellable_provider"),
        {"comment": "SellableOffering:ProviderOffering = 1:N 연결"},
    )

    sellable_offering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sellable_offerings.id"),
        nullable=False,
        index=True,
    )
    provider_offering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_offerings.id"),
        nullable=False,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="이 SellableOffering의 기본 실행처 여부",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="라우팅 우선순위 (낮을수록 우선)",
    )
    routing_conditions: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment='[가정] 라우팅 조건 미확정 → JSONB. 예: {"region": "서울"}',
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Relations
    sellable_offering: Mapped["SellableOffering"] = relationship(
        "SellableOffering", back_populates="provider_mappings"
    )
    provider_offering: Mapped["ProviderOffering"] = relationship(
        "ProviderOffering", back_populates="sellable_mappings"
    )

    def __repr__(self) -> str:
        return (
            f"<SellableProviderMapping "
            f"{self.sellable_offering_id} → {self.provider_offering_id}>"
        )
