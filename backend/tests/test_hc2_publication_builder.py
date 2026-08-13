from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.models import CafeTable, MenuCategory, MenuItem, PreparationArea, TableQRToken
from app.services.cafe_cloud_publication import build_cafe_publication
from tests.p5_fixtures import seed_p5_test_data


def test_cafe_publication_uses_explicit_customer_safe_allowlist(
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    with db_session_factory() as db:
        category = MenuCategory(
            company_id=ids["cafe_company"],
            branch_id=None,
            name="Cloud Safe Drinks",
            display_order=1,
            is_active=True,
        )
        db.add(category)
        db.flush()
        item = MenuItem(
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            category_id=category.id,
            product_id=ids["cafe_product"],
            name="Safe Latte",
            description="Customer-visible description",
            selling_price=Decimal("175.00"),
            preparation_area=PreparationArea.BEVERAGE,
            available=True,
            is_active=True,
            display_order=1,
        )
        table = CafeTable(
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            table_code="PUB01",
            display_name="Publication Table",
            capacity=4,
            is_active=True,
        )
        db.add_all([item, table])
        db.flush()
        digest = hashlib.sha256(b"publication-proof").hexdigest()
        db.add(
            TableQRToken(
                company_id=ids["cafe_company"],
                branch_id=ids["cafe_branch"],
                table_id=table.id,
                public_reference="publication-table-reference",
                token_hash=digest,
                token_prefix="publicatio",
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
        )
        db.commit()

        publication = build_cafe_publication(
            db,
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            version=1,
        )

    assert publication.company_id == str(ids["cafe_company"])
    assert publication.branch_id == str(ids["cafe_branch"])
    assert any(row.name == "Safe Latte" for row in publication.items)
    assert publication.tables[0].verifier_digest == digest
    assert publication.tables[0].public_reference == "publication-table-reference"
    assert publication.availability[0].available is True

    item_keys = set(publication.items[0].model_dump().keys())
    assert item_keys == {
        "source_menu_item_id",
        "source_product_id",
        "source_category_id",
        "name",
        "description",
        "image_reference",
        "selling_price",
        "preparation_area",
        "available",
        "display_order",
    }
    table_keys = set(publication.tables[0].model_dump().keys())
    assert table_keys == {
        "source_table_id",
        "table_code",
        "table_display_name",
        "public_reference",
        "verifier_digest",
        "valid_until",
        "disabled_at",
        "available",
    }
    availability_keys = set(publication.availability[0].model_dump().keys())
    assert availability_keys == {"source_product_id", "available"}
    assert isinstance(publication.availability[0].available, bool)


def test_retail_scope_is_rejected_by_cafe_publication_builder(
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    with db_session_factory() as db:
        with pytest.raises(HTTPException, match="Cafe"):
            build_cafe_publication(
                db,
                company_id=1,
                branch_id=ids["retail_branch"],
                version=1,
            )
