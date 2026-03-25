"""Provider / Offering / StandardProductType 스키마"""
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Provider ────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider_type: Optional[str] = Field(
        default=None,
        description="media_company | individual | internal [가정: 미확정]"
    )
    contact_info: Optional[dict[str, Any]] = None
    is_active: bool = True
    note: Optional[str] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    contact_info: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


class ProviderResponse(BaseModel):
    id: uuid.UUID
    name: str
    provider_type: Optional[str]
    contact_info: Optional[dict[str, Any]]
    is_active: bool
    note: Optional[str]

    model_config = {"from_attributes": True}


# ── StandardProductType ─────────────────────────────────────────

class StandardProductTypeCreate(BaseModel):
    """[초안/제안안] 확정본 아님"""
    code: str = Field(max_length=100)
    display_name: str = Field(max_length=200)
    description: Optional[str] = None
    channel: Optional[str] = None
    requires_period: bool = True
    requires_daily_qty: bool = False
    supports_subtype: bool = False
    is_active: bool = True
    sort_order: int = 0


class StandardProductTypeResponse(BaseModel):
    id: uuid.UUID
    code: str
    display_name: str
    description: Optional[str]
    channel: Optional[str]
    requires_period: bool
    requires_daily_qty: bool
    supports_subtype: bool
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


# ── SellableOffering ─────────────────────────────────────────────

class SellableOfferingCreate(BaseModel):
    standard_product_type_id: uuid.UUID
    name: str = Field(max_length=300)
    description: Optional[str] = None
    base_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[dict[str, Any]] = None
    is_active: bool = True
    note: Optional[str] = None


class SellableOfferingUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


class SellableOfferingResponse(BaseModel):
    id: uuid.UUID
    standard_product_type_id: uuid.UUID
    name: str
    description: Optional[str]
    base_price: Optional[int]
    unit: Optional[str]
    spec_data: Optional[dict[str, Any]]
    is_active: bool

    model_config = {"from_attributes": True}


# ── ProviderOffering ─────────────────────────────────────────────

class ProviderOfferingCreate(BaseModel):
    standard_product_type_id: uuid.UUID
    provider_id: uuid.UUID
    name: str = Field(max_length=300)
    cost_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[dict[str, Any]] = None
    is_active: bool = True
    note: Optional[str] = None


class ProviderOfferingResponse(BaseModel):
    id: uuid.UUID
    standard_product_type_id: uuid.UUID
    provider_id: uuid.UUID
    name: str
    cost_price: Optional[int]
    unit: Optional[str]
    spec_data: Optional[dict[str, Any]]
    is_active: bool

    model_config = {"from_attributes": True}


# ── SellableProviderMapping ──────────────────────────────────────

class MappingCreate(BaseModel):
    sellable_offering_id: uuid.UUID
    provider_offering_id: uuid.UUID
    is_default: bool = False
    priority: int = 0
    routing_conditions: Optional[dict[str, Any]] = Field(
        default=None, description="[가정] 라우팅 조건 미확정 → JSONB"
    )
    is_active: bool = True


class MappingResponse(BaseModel):
    id: uuid.UUID
    sellable_offering_id: uuid.UUID
    provider_offering_id: uuid.UUID
    is_default: bool
    priority: int
    routing_conditions: Optional[dict[str, Any]]
    is_active: bool

    model_config = {"from_attributes": True}
