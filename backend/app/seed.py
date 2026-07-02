"""Idempotent seed data: chart of accounts, tax codes, company row, sequences.

Run with:  python -m app.seed
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import (
    Account,
    AccountType,
    CompanySettings,
    DocumentSequence,
    TaxCode,
)

ACCOUNTS = [
    # (code, name, type, is_system)
    ("1000", "Cash on Hand", AccountType.ASSET, True),
    ("1100", "Bank", AccountType.ASSET, True),
    ("1200", "Accounts Receivable", AccountType.ASSET, True),
    ("2100", "GST Output Tax", AccountType.LIABILITY, True),
    ("3000", "Retained Earnings", AccountType.EQUITY, True),
    ("4000", "Sales Revenue", AccountType.REVENUE, True),
]

SEQUENCES = [
    # (doc_type, prefix)
    ("QUOTATION", "QT-"),
    ("INVOICE", "INV-"),
    ("PAYMENT", "RCT-"),
    ("CREDIT_NOTE", "CN-"),
    ("JOURNAL", "JE-"),
]


def get_or_create_account(
    session: Session, code: str, name: str, type_: AccountType, is_system: bool
) -> Account:
    account = session.scalar(select(Account).where(Account.code == code))
    if account is None:
        account = Account(code=code, name=name, type=type_, is_system=is_system)
        session.add(account)
        session.flush()
    return account


def seed(session: Session) -> None:
    for code, name, type_, is_system in ACCOUNTS:
        get_or_create_account(session, code, name, type_, is_system)

    gst_output = session.scalar(select(Account).where(Account.code == "2100"))
    tax_codes = [
        ("SR", "Standard-Rated (9%)", Decimal("9.00"), gst_output.id),
        ("ZR", "Zero-Rated", Decimal("0.00"), None),
        ("ES", "Exempt Supply", Decimal("0.00"), None),
    ]
    for code, name, rate, account_id in tax_codes:
        if session.scalar(select(TaxCode).where(TaxCode.code == code)) is None:
            session.add(TaxCode(code=code, name=name, rate=rate, account_id=account_id))

    for doc_type, prefix in SEQUENCES:
        if session.get(DocumentSequence, doc_type) is None:
            session.add(DocumentSequence(doc_type=doc_type, prefix=prefix))

    if session.get(CompanySettings, 1) is None:
        session.add(CompanySettings(id=1, name="My Company Pte Ltd", fy_start_month=1))


def main() -> None:
    with SessionLocal() as session:
        seed(session)
        session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    main()
