from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ============================================================
# CREATE ASSET
# ============================================================

class AssetCreate(BaseModel):
    product_name: str

    brand: str | None = None

    model_number: str | None = None

    serial_number: str | None = None

    purchase_date: date | None = None

    purchase_price: float | None = None

    currency: str = "INR"

    warranty_months: int | None = None

    seller: str | None = None

    invoice_number: str | None = None


# ============================================================
# CONFIRM ASSET
# ============================================================

class AssetConfirm(AssetCreate):
    """
    Data submitted after the user reviews
    and confirms OCR-extracted information.
    """

    receipt_path: str | None = None


# ============================================================
# UPDATE ASSET
# ============================================================

class AssetUpdate(BaseModel):
    product_name: str | None = None

    brand: str | None = None

    model_number: str | None = None

    serial_number: str | None = None

    purchase_date: date | None = None

    purchase_price: float | None = None

    currency: str | None = None

    warranty_months: int | None = None

    seller: str | None = None

    invoice_number: str | None = None


# ============================================================
# RESPONSE
# ============================================================

class AssetResponse(BaseModel):
    id: int

    product_name: str

    brand: str | None = None

    model_number: str | None = None

    serial_number: str | None = None

    purchase_date: date | None = None

    purchase_price: float | None = None

    currency: str

    warranty_months: int | None = None

    warranty_expiry: date | None = None

    seller: str | None = None

    invoice_number: str | None = None

    receipt_path: str | None = None

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )