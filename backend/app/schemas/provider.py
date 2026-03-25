"""
Provider / StandardProductType / SellableOffering / ProviderOffering 스키마
"""
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


# ── Provider ──────────────────────────────────────────────
class ProviderCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    provider_type: Optional[str] = Field(
        default=None,
        description="media_company | individual | internal",
    )
    contact_info: Optional[Dict[str, Any]] = None
    note: Optional[str] = None


class ProviderUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    provider_type: Optional[str] = None
    contact_info: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


class ProviderRead(BaseSchema):
    id: UUID
    name: str
    provider_type: Optional[str]
    contact_info: Optional[Dict[str, Any]]
    is_active: bool
    note: Optional[str]


# ── StandardProductType ───────────────────────────────────
class StandardProductTypeCreate(BaseSchema):
    code: str = Field(
        min_length=1,
        max_length=100,
        description="TRAFFIC | SAVE | AI_REAL | AI_NONREAL | BLOG_REPORTER | BLOG_DISPATCH | XIAOHONGSHU | DIANPING",
    )
    display_name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    channel: Optional[str] = None
    requires_period: bool = True
    requires_daily_qty: bool = False
    supports_subtype: bool = False
    sort_order: int = 0


class StandardProductTypeRead(BaseSchema):
    id: UUID
    code: str
    display_name: str
    description: Optional[str]
    channel: Optional[str]
    requires_period: bool
    requires_daily_qty: bool
    supports_subtype: bool
    is_active: bool
    sort_order: int


# ── SellableOffering ──────────────────────────────────────
class SellableOfferingCreate(BaseSchema):
    standard_product_type_id: UUID
    name: str = Field(min_length=1, max_length=300)
    description: Optional[str] = None
    base_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[Dict[str, Any]] = None
    note: Optional[str] = None


class SellableOfferingUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    base_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


class SellableOfferingRead(BaseSchema):
    id: UUID
    standard_product_type_id: UUID
    name: str
    description: Optional[str]
    base_price: Optional[int]
    unit: Optional[str]
    spec_data: Optional[Dict[str, Any]]
    is_active: bool
    note: Optional[str]


# ── ProviderOffering ──────────────────────────────────────
class ProviderOfferingCreate(BaseSchema):
    standard_product_type_id: UUID
    provider_id: UUID
    name: str = Field(min_length=1, max_length=300)
    cost_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[Dict[str, Any]] = None
    note: Optional[str] = None


class ProviderOfferingUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    cost_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


class ProviderOfferingRead(BaseSchema):
    id: UUID
    standard_product_type_id: UUID
    provider_id: UUID
    name: str
    cost_price: Optional[int]
    unit: Optional[str]
    spec_data: Optional[Dict[str, Any]]
    is_active: bool
    note: Optional[str]


# ── SellableProviderMapping ───────────────────────────────
class MappingCreate(BaseSchema):
    sellable_offering_id: UUID
    provider_offering_id: UUID
    is_default: bool = False
    priority: int = 0
    routing_conditions: Optional[Dict[str, Any]] = None


class MappingRead(BaseSchema):
    id: UUID
    sellable_offering_id: UUID
    provider_offering_id: UUID
    is_default: bool
    priority: int
    routing_conditions: Optional[Dict[str, Any]]
    is_active: bool


# ── Agency / Brand (Wave 1 최소) ──────────────────────────
class AgencyCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    note: Optional[str] = None


class AgencyRead(BaseSchema):
    id: UUID
    name: str
    note: Optional[str]
    is_active: bool


class BrandCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    agency_id: Optional[UUID] = None
    note: Optional[str] = None


class BrandRead(BaseSchema):
    id: UUID
    name: str
    agency_id: Optional[UUID]
    note: Optional[str]
    is_active: bool
