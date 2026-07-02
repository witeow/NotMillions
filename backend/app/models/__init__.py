# Every model must be imported here so Base.metadata (and therefore Alembic
# autogenerate) sees the full schema.
from app.models.account import Account, AccountType
from app.models.company import CompanySettings
from app.models.credit_note import (
    CreditNote,
    CreditNoteAllocation,
    CreditNoteLine,
    CreditNoteStatus,
)
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.item import Item
from app.models.journal import JournalEntry, JournalLine, JournalSourceType
from app.models.payment import (
    Payment,
    PaymentAllocation,
    PaymentMethod,
    PaymentStatus,
)
from app.models.quotation import Quotation, QuotationLine, QuotationStatus
from app.models.sequence import DocumentSequence, next_document_number
from app.models.tax_code import TaxCode

__all__ = [
    "Account",
    "AccountType",
    "CompanySettings",
    "CreditNote",
    "CreditNoteAllocation",
    "CreditNoteLine",
    "CreditNoteStatus",
    "Customer",
    "DocumentSequence",
    "Invoice",
    "InvoiceLine",
    "InvoiceStatus",
    "Item",
    "JournalEntry",
    "JournalLine",
    "JournalSourceType",
    "Payment",
    "PaymentAllocation",
    "PaymentMethod",
    "PaymentStatus",
    "Quotation",
    "QuotationLine",
    "QuotationStatus",
    "TaxCode",
    "next_document_number",
]
