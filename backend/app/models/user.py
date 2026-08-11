from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.branch import Branch
    from app.models.chat import AIChatSession
    from app.models.inventory import StockMovement
    from app.models.purchase_order import PurchaseOrder
    from app.models.sale import Sale


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    STORE_MANAGER = "store_manager"
    STAFF = "staff"
    ANALYST = "analyst"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    branch: Mapped[Branch | None] = relationship(back_populates="users")
    sales: Mapped[list[Sale]] = relationship(back_populates="creator")
    stock_movements: Mapped[list[StockMovement]] = relationship(back_populates="creator")
    created_purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        back_populates="creator",
        foreign_keys="PurchaseOrder.created_by",
    )
    approved_purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        back_populates="approver",
        foreign_keys="PurchaseOrder.approved_by",
    )
    ai_chat_sessions: Mapped[list[AIChatSession]] = relationship(back_populates="user")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")

    __table_args__ = (Index("ix_users_branch_id", "branch_id"),)
