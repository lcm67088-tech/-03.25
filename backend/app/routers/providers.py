"""
Provider / StandardProductType / SellableOffering / ProviderOffering 라우터
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import AdminUser, CurrentUser, DBSession, OperatorUser
from app.models.provider import (
    Provider,
    ProviderOffering,
    SellableOffering,
    SellableProviderMapping,
    StandardProductType,
)
from app.models.agency import Agency, Brand
from app.schemas.common import MessageResponse
from app.schemas.provider import (
    AgencyCreate,
    AgencyRead,
    BrandCreate,
    BrandRead,
    MappingCreate,
    MappingRead,
    ProviderCreate,
    ProviderOfferingCreate,
    ProviderOfferingRead,
    ProviderOfferingUpdate,
    ProviderRead,
    ProviderUpdate,
    SellableOfferingCreate,
    SellableOfferingRead,
    SellableOfferingUpdate,
    StandardProductTypeCreate,
    StandardProductTypeRead,
)


# ── Provider ──────────────────────────────────────────────
provider_router = APIRouter(prefix="/providers", tags=["providers"])


@provider_router.get("/", response_model=list[ProviderRead])
async def list_providers(db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(Provider).where(Provider.is_active == True).order_by(Provider.name)  # noqa: E712
    )
    return result.scalars().all()


@provider_router.post("/", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(body: ProviderCreate, db: DBSession, current_user: OperatorUser):
    provider = Provider(**body.model_dump(exclude_none=True))
    db.add(provider)
    await db.flush()
    await db.refresh(provider)
    return provider


@provider_router.get("/{provider_id}", response_model=ProviderRead)
async def get_provider(provider_id: UUID, db: DBSession, current_user: CurrentUser):
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    return p


@provider_router.patch("/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: UUID, body: ProviderUpdate, db: DBSession, current_user: OperatorUser
):
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    await db.flush()
    await db.refresh(p)
    return p


# ── StandardProductType ───────────────────────────────────
spt_router = APIRouter(prefix="/standard-product-types", tags=["standard-product-types"])


@spt_router.get("/", response_model=list[StandardProductTypeRead])
async def list_standard_product_types(db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(StandardProductType)
        .where(StandardProductType.is_active == True)  # noqa: E712
        .order_by(StandardProductType.sort_order, StandardProductType.code)
    )
    return result.scalars().all()


@spt_router.post("/", response_model=StandardProductTypeRead, status_code=status.HTTP_201_CREATED)
async def create_standard_product_type(
    body: StandardProductTypeCreate, db: DBSession, current_user: AdminUser
):
    """StandardProductType 생성 (ADMIN 전용)"""
    existing = await db.execute(
        select(StandardProductType).where(StandardProductType.code == body.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Code '{body.code}' already exists",
        )
    spt = StandardProductType(**body.model_dump())
    db.add(spt)
    await db.flush()
    await db.refresh(spt)
    return spt


@spt_router.get("/{spt_id}", response_model=StandardProductTypeRead)
async def get_standard_product_type(
    spt_id: UUID, db: DBSession, current_user: CurrentUser
):
    result = await db.execute(
        select(StandardProductType).where(StandardProductType.id == spt_id)
    )
    spt = result.scalar_one_or_none()
    if not spt:
        raise HTTPException(status_code=404, detail="StandardProductType not found")
    return spt


# ── SellableOffering ──────────────────────────────────────
sellable_router = APIRouter(prefix="/sellable-offerings", tags=["sellable-offerings"])


@sellable_router.get("/", response_model=list[SellableOfferingRead])
async def list_sellable_offerings(db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(SellableOffering).where(SellableOffering.is_active == True)  # noqa: E712
    )
    return result.scalars().all()


@sellable_router.post("/", response_model=SellableOfferingRead, status_code=status.HTTP_201_CREATED)
async def create_sellable_offering(
    body: SellableOfferingCreate, db: DBSession, current_user: OperatorUser
):
    so = SellableOffering(**body.model_dump(exclude_none=True))
    db.add(so)
    await db.flush()
    await db.refresh(so)
    return so


@sellable_router.get("/{so_id}", response_model=SellableOfferingRead)
async def get_sellable_offering(so_id: UUID, db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(SellableOffering).where(SellableOffering.id == so_id)
    )
    so = result.scalar_one_or_none()
    if not so:
        raise HTTPException(status_code=404, detail="SellableOffering not found")
    return so


@sellable_router.patch("/{so_id}", response_model=SellableOfferingRead)
async def update_sellable_offering(
    so_id: UUID, body: SellableOfferingUpdate, db: DBSession, current_user: OperatorUser
):
    result = await db.execute(
        select(SellableOffering).where(SellableOffering.id == so_id)
    )
    so = result.scalar_one_or_none()
    if not so:
        raise HTTPException(status_code=404, detail="SellableOffering not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(so, field, value)
    await db.flush()
    await db.refresh(so)
    return so


# ── ProviderOffering ──────────────────────────────────────
po_router = APIRouter(prefix="/provider-offerings", tags=["provider-offerings"])


@po_router.get("/", response_model=list[ProviderOfferingRead])
async def list_provider_offerings(db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(ProviderOffering).where(ProviderOffering.is_active == True)  # noqa: E712
    )
    return result.scalars().all()


@po_router.post("/", response_model=ProviderOfferingRead, status_code=status.HTTP_201_CREATED)
async def create_provider_offering(
    body: ProviderOfferingCreate, db: DBSession, current_user: OperatorUser
):
    po = ProviderOffering(**body.model_dump(exclude_none=True))
    db.add(po)
    await db.flush()
    await db.refresh(po)
    return po


@po_router.patch("/{po_id}", response_model=ProviderOfferingRead)
async def update_provider_offering(
    po_id: UUID, body: ProviderOfferingUpdate, db: DBSession, current_user: OperatorUser
):
    result = await db.execute(
        select(ProviderOffering).where(ProviderOffering.id == po_id)
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="ProviderOffering not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(po, field, value)
    await db.flush()
    await db.refresh(po)
    return po


# ── SellableProviderMapping ───────────────────────────────
mapping_router = APIRouter(prefix="/mappings", tags=["mappings"])


@mapping_router.get("/", response_model=list[MappingRead])
async def list_mappings(db: DBSession, current_user: CurrentUser):
    result = await db.execute(select(SellableProviderMapping))
    return result.scalars().all()


@mapping_router.post("/", response_model=MappingRead, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    body: MappingCreate, db: DBSession, current_user: OperatorUser
):
    m = SellableProviderMapping(**body.model_dump(exclude_none=True))
    db.add(m)
    await db.flush()
    await db.refresh(m)
    return m


@mapping_router.delete("/{mapping_id}", response_model=MessageResponse)
async def delete_mapping(
    mapping_id: UUID, db: DBSession, current_user: OperatorUser
):
    result = await db.execute(
        select(SellableProviderMapping).where(SellableProviderMapping.id == mapping_id)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mapping not found")
    m.is_active = False
    return MessageResponse(message="Mapping deactivated")


# ── Agency ────────────────────────────────────────────────
agency_router = APIRouter(prefix="/agencies", tags=["agencies"])


@agency_router.get("/", response_model=list[AgencyRead])
async def list_agencies(db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(Agency).where(Agency.is_active == True).order_by(Agency.name)  # noqa: E712
    )
    return result.scalars().all()


@agency_router.post("/", response_model=AgencyRead, status_code=status.HTTP_201_CREATED)
async def create_agency(body: AgencyCreate, db: DBSession, current_user: OperatorUser):
    agency = Agency(**body.model_dump(exclude_none=True))
    db.add(agency)
    await db.flush()
    await db.refresh(agency)
    return agency


# ── Brand ─────────────────────────────────────────────────
brand_router = APIRouter(prefix="/brands", tags=["brands"])


@brand_router.get("/", response_model=list[BrandRead])
async def list_brands(db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(Brand).where(Brand.is_active == True).order_by(Brand.name)  # noqa: E712
    )
    return result.scalars().all()


@brand_router.post("/", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
async def create_brand(body: BrandCreate, db: DBSession, current_user: OperatorUser):
    brand = Brand(**body.model_dump(exclude_none=True))
    db.add(brand)
    await db.flush()
    await db.refresh(brand)
    return brand
