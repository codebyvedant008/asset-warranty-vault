from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    product_name: Mapped[str] = mapped_column(
        String(200),
        index=True
    )

    brand: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    model_number: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    serial_number: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    purchase_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    purchase_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    currency: Mapped[str] = mapped_column(
        String(8),
        default="INR"
    )

    warranty_months: Mapped[int | None] = mapped_column(
        nullable=True
    )

    warranty_expiry: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    seller: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True
    )

    invoice_number: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    receipt_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )