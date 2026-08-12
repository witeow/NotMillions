# Every model must be imported here so Base.metadata (and therefore Alembic
# autogenerate) sees the full schema.
from app.models.account import Account, AccountType
from app.models.bill import Bill, BillLine, BillStatus
from app.models.company import CompanySettings
from app.models.credit_note import (
    CreditNote,
    CreditNoteAllocation,
    CreditNoteLine,
    CreditNoteStatus,
)
from app.models.customer import Customer
from app.models.debit_note import (
    DebitNote,
    DebitNoteAllocation,
    DebitNoteLine,
    DebitNoteStatus,
)
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.item import Item
from app.models.journal import JournalEntry, JournalLine, JournalSourceType
from app.models.payment import (
    Payment,
    PaymentAllocation,
    PaymentMethod,
    PaymentStatus,
)
from app.models.payment_made import (
    PaymentMade,
    PaymentMadeAllocation,
    PaymentMadeStatus,
)
from app.models.quotation import Quotation, QuotationLine, QuotationStatus
from app.models.sequence import DocumentSequence, next_document_number
from app.models.supplier import Supplier
from app.models.tax_code import TaxCode

__all__ = [
    "Account",
    "AccountType",
    "Bill",
    "BillLine",
    "BillStatus",
    "CompanySettings",
    "CreditNote",
    "CreditNoteAllocation",
    "CreditNoteLine",
    "CreditNoteStatus",
    "Customer",
    "DebitNote",
    "DebitNoteAllocation",
    "DebitNoteLine",
    "DebitNoteStatus",
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
    "PaymentMade",
    "PaymentMadeAllocation",
    "PaymentMadeStatus",
    "PaymentStatus",
    "Quotation",
    "QuotationLine",
    "QuotationStatus",
    "Supplier",
    "TaxCode",
    "next_document_number",
]
