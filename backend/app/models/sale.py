from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.product import Product
    from app.models.user import User


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    sale_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    branch: Mapped[Branch] = relationship(back_populates="sales")
    creator: Mapped[User] = relationship(back_populates="sales")
    items: Mapped[list[SaleItem]] = relationship(back_populates="sale", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sales_branch_id", "branch_id"),
        Index("ix_sales_sale_datetime", "sale_datetime"),
        Index("ix_sales_created_by", "created_by"),
    )


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    sale: Mapped[Sale] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="sale_items")

    __table_args__ = (
        Index("ix_sale_items_sale_id", "sale_id"),
        Index("ix_sale_items_product_id", "product_id"),
    )
