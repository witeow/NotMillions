from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.models import (
    Account,
    AccountType,
    Customer,
    DocumentSequence,
    Item,
    TaxCode,
)
from app.seed import seed

TEST_DB = "notmillions_test"
ADMIN_URL = "postgresql+psycopg://notmillions:notmillions@localhost:5432/postgres"
TEST_URL = f"postgresql+psycopg://notmillions:notmillions@localhost:5432/{TEST_DB}"


@pytest.fixture(scope="session")
def engine():
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    admin_engine.dispose()

    test_engine = create_engine(TEST_URL)
    Base.metadata.create_all(test_engine)

    _seed_session = sessionmaker(bind=test_engine)()
    seed(_seed_session)
    _seed_session.commit()
    _seed_session.close()

    yield test_engine

    test_engine.dispose()
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
    admin_engine.dispose()


@pytest.fixture()
def db(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_customer(db: Session, **overrides) -> Customer:
    defaults = dict(code="CUST-TEST", name="Test Customer Pte Ltd")
    defaults.update(overrides)
    obj = Customer(**defaults)
    db.add(obj)
    db.flush()
    return obj


def make_supplier(db: Session, **overrides):
    from app.models import Supplier
    defaults = dict(code="SUP-TEST", name="Test Supplier Pte Ltd")
    defaults.update(overrides)
    obj = Supplier(**defaults)
    db.add(obj)
    db.flush()
    return obj


def make_item(db: Session, *, income_account_id: int | None = None, **overrides) -> Item:
    if income_account_id is None:
        sales = db.execute(
            text("SELECT id FROM accounts WHERE code = '4000'")
        ).scalar_one()
        income_account_id = sales
    sr = db.execute(text("SELECT id FROM tax_codes WHERE code = 'SR'")).scalar_one()
    defaults = dict(
        code="ITEM-TEST",
        description="Test item",
        unit_price=Decimal("100.0000"),
        default_tax_code_id=sr,
        income_account_id=income_account_id,
    )
    defaults.update(overrides)
    obj = Item(**defaults)
    db.add(obj)
    db.flush()
    return obj


def _get_account(db: Session, code: str) -> int:
    return db.execute(
        text("SELECT id FROM accounts WHERE code = :code"), {"code": code}
    ).scalar_one()


def _get_tax_code(db: Session, code: str) -> TaxCode:
    from sqlalchemy import select
    return db.execute(select(TaxCode).where(TaxCode.code == code)).scalar_one()
