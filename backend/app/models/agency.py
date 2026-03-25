"""
Agency / Brand 모델
Wave 1: 테이블 구조만 생성. 강한 FK 운영은 Wave 2 이후.
취합 시트의 '대행사명', '브랜드' 컬럼에 대응하는 미래 엔티티.
"""
import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Agency(BaseModel):
    """
    대행사 (취합 시트 '대행사명' 컬럼 대응)
    Wave 1: 테이블 존재. nullable FK. 강제 운영은 Wave 2 이후.
    """
    __tablename__ = "agencies"
    __table_args__ = {
        "comment": "대행사 정보. Wave 1: 테이블 생성만. FK 강제는 Wave 2 이후."
    }

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="대행사명",
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="메모",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    def __repr__(self) -> str:
        return f"<Agency {self.name}>"


class Brand(BaseModel):
    """
    브랜드 (취합 시트 '브랜드' 컬럼 대응 — 스마일, 팡팡 등)
    Wave 1: 테이블 존재. nullable FK. 강제 운영은 Wave 2 이후.
    [가정] Brand-Agency 관계 미확정 → nullable FK
    """
    __tablename__ = "brands"
    __table_args__ = {
        "comment": "브랜드 정보. Wave 1: 테이블 생성만. FK 강제는 Wave 2 이후."
    }

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="브랜드명",
    )
    agency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="소속 대행사 FK (nullable, 가정: 관계 미확정)",
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    agency: Mapped[Optional["Agency"]] = relationship("Agency")

    def __repr__(self) -> str:
        return f"<Brand {self.name}>"
