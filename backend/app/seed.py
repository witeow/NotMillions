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
    # Assets
    ("1000", "Cash on Hand", AccountType.ASSET, True),
    ("1100", "Bank", AccountType.ASSET, True),
    ("1200", "Accounts Receivable", AccountType.ASSET, True),
    ("1300", "GST Input Tax", AccountType.ASSET, True),
    # Liabilities
    ("2000", "Accounts Payable", AccountType.LIABILITY, True),
    ("2100", "GST Output Tax", AccountType.LIABILITY, True),
    # Equity
    ("3000", "Retained Earnings", AccountType.EQUITY, True),
    # Revenue
    ("4000", "Sales Revenue", AccountType.REVENUE, True),
    # Direct costs (5000s — COGS for construction)
    ("5000", "Cost of Materials", AccountType.EXPENSE, False),
    ("5100", "Subcontractor Costs", AccountType.EXPENSE, False),
    ("5200", "Equipment Rental", AccountType.EXPENSE, False),
    # Operating expenses (6000s)
    ("6000", "Wages & Salaries", AccountType.EXPENSE, False),
    ("6100", "CPF Contributions", AccountType.EXPENSE, False),
    ("6200", "Foreign Worker Levy", AccountType.EXPENSE, False),
    ("6300", "Office Expenses", AccountType.EXPENSE, False),
]

SEQUENCES = [
    # (doc_type, prefix)
    ("QUOTATION", "QT-"),
    ("INVOICE", "INV-"),
    ("PAYMENT", "RCT-"),
    ("CREDIT_NOTE", "CN-"),
    ("JOURNAL", "JE-"),
    ("BILL", "BILL-"),
    ("PAYMENT_MADE", "PMT-"),
    ("DEBIT_NOTE", "DN-"),
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
    gst_input = session.scalar(select(Account).where(Account.code == "1300"))
    tax_codes = [
        # Output tax (sales)
        ("SR", "Standard-Rated (9%)", Decimal("9.00"), gst_output.id),
        ("ZR", "Zero-Rated", Decimal("0.00"), None),
        ("ES", "Exempt Supply", Decimal("0.00"), None),
        # Input tax (purchases)
        ("TX", "Standard-Rated Input (9%)", Decimal("9.00"), gst_input.id),
        ("BL", "Blocked Input Tax", Decimal("0.00"), None),
        ("NR", "Not Registered", Decimal("0.00"), None),
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
