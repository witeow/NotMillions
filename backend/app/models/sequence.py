from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


class DocumentSequence(Base):
    __tablename__ = "document_sequences"

    doc_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    prefix: Mapped[str] = mapped_column(String(10))
    next_number: Mapped[int] = mapped_column(default=1)
    padding: Mapped[int] = mapped_column(default=4)


def next_document_number(session: Session, doc_type: str) -> str:
    """Issue the next number for a document type, e.g. INV-0001.

    Row-locks the sequence so concurrent requests can't issue duplicates.
    Must be called inside the same transaction that saves the document.
    """
    seq = session.execute(
        select(DocumentSequence)
        .where(DocumentSequence.doc_type == doc_type)
        .with_for_update()
    ).scalar_one()
    number = f"{seq.prefix}{seq.next_number:0{seq.padding}d}"
    seq.next_number += 1
    return number
