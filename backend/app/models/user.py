"""
User 모델
역할: ADMIN | OPERATOR (Wave 1 확정)
VIEWER는 후속 추가 예정 (VARCHAR이므로 스키마 변경 불필요)
REVIEWER는 확정 역할 아님 — 포함하지 않음
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class User(BaseModel):
    """
    내부 운영자 계정
    Wave 1 역할 체계: ADMIN | OPERATOR
    검수 기능은 OPERATOR가 수행 (별도 REVIEWER 역할 없음)
    """
    __tablename__ = "users"
    __table_args__ = {"comment": "내부 운영자 계정"}

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="로그인 이메일",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="운영자 이름",
    )
    hashed_pw: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt 해시 비밀번호",
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="OPERATOR",
        server_default="OPERATOR",
        index=True,
        comment=(
            "Wave 1 확정 역할: ADMIN | OPERATOR. "
            "VIEWER는 후속 추가 예정. "
            "REVIEWER는 확정 역할 아님."
        ),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="계정 활성화 여부",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="마지막 로그인 시각",
    )

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role}]>"

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    @property
    def is_operator(self) -> bool:
        return self.role in ("ADMIN", "OPERATOR")
