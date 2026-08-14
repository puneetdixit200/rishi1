"""add Cafe billing source, idempotency, and billed links

Revision ID: 20260814_0015
Revises: 20260814_0014
Create Date: 2026-08-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260814_0015"
down_revision: str | None = "20260814_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("source_type", sa.String(length=40), nullable=True))
    op.add_column("invoices", sa.Column("source_id", sa.String(length=64), nullable=True))
    op.add_column(
        "invoices", sa.Column("billing_idempotency_key_hash", sa.String(length=64), nullable=True)
    )
    op.add_column("invoices", sa.Column("billing_request_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_invoices_company_billing_idempotency",
        "invoices",
        ["company_id", "billing_idempotency_key_hash"],
    )
    op.create_index(
        "ix_invoices_company_source",
        "invoices",
        ["company_id", "source_type", "source_id"],
        unique=False,
    )
    op.create_index(
        "uq_invoices_active_cafe_source",
        "invoices",
        ["company_id", "source_type", "source_id"],
        unique=True,
        postgresql_where=sa.text(
            "source_type IS NOT NULL AND source_id IS NOT NULL AND status NOT IN ('cancelled', 'returned')"
        ),
        sqlite_where=sa.text(
            "source_type IS NOT NULL AND source_id IS NOT NULL AND status NOT IN ('cancelled', 'returned')"
        ),
    )

    op.alter_column("invoice_items", "product_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("sale_items", "product_id", existing_type=sa.Integer(), nullable=True)

    op.add_column("table_sessions", sa.Column("billed_invoice_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_table_sessions_billed_invoice_id_invoices",
        "table_sessions",
        "invoices",
        ["billed_invoice_id"],
        ["id"],
    )
    op.create_index(
        "ix_table_sessions_billed_invoice_id", "table_sessions", ["billed_invoice_id"], unique=False
    )
    op.create_index(
        "ix_cafe_orders_billed_invoice_id", "cafe_orders", ["billed_invoice_id"], unique=False
    )
    op.create_index(
        "ix_cafe_order_items_billed_invoice_item_id",
        "cafe_order_items",
        ["billed_invoice_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cafe_order_items_billed_invoice_item_id", table_name="cafe_order_items")
    op.drop_index("ix_cafe_orders_billed_invoice_id", table_name="cafe_orders")
    op.drop_index("ix_table_sessions_billed_invoice_id", table_name="table_sessions")
    op.drop_constraint(
        "fk_table_sessions_billed_invoice_id_invoices", "table_sessions", type_="foreignkey"
    )
    op.drop_column("table_sessions", "billed_invoice_id")

    op.alter_column("sale_items", "product_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("invoice_items", "product_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("uq_invoices_active_cafe_source", table_name="invoices")
    op.drop_index("ix_invoices_company_source", table_name="invoices")
    op.drop_constraint("uq_invoices_company_billing_idempotency", "invoices", type_="unique")
    op.drop_column("invoices", "billing_request_hash")
    op.drop_column("invoices", "billing_idempotency_key_hash")
    op.drop_column("invoices", "source_id")
    op.drop_column("invoices", "source_type")
