from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, User, UserRole


@pytest.fixture()
def db_session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def seed_auth_data(db_session_factory: sessionmaker[Session]) -> None:
    with db_session_factory() as db:
        central_branch = Branch(
            name="Central Market",
            address="14 MG Road",
            city="Bengaluru",
            manager_name="Ananya Rao",
        )
        db.add(central_branch)
        db.flush()
        db.add_all(
            [
                User(
                    name="Admin User",
                    email="admin@hybridretail.test",
                    password_hash=hash_password("RetailDemo@123"),
                    role=UserRole.ADMIN,
                ),
                User(
                    name="Store Manager",
                    email="manager@hybridretail.test",
                    password_hash=hash_password("RetailDemo@123"),
                    role=UserRole.STORE_MANAGER,
                    branch_id=central_branch.id,
                ),
                User(
                    name="Staff User",
                    email="staff@hybridretail.test",
                    password_hash=hash_password("RetailDemo@123"),
                    role=UserRole.STAFF,
                    branch_id=central_branch.id,
                ),
                User(
                    name="Analyst User",
                    email="analyst@hybridretail.test",
                    password_hash=hash_password("RetailDemo@123"),
                    role=UserRole.ANALYST,
                ),
            ]
        )
        db.commit()


@pytest.fixture()
def client(
    db_session_factory: sessionmaker[Session],
    seed_auth_data: None,
) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with db_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
