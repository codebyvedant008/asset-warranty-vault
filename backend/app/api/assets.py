from calendar import monthrange
from datetime import date
from pathlib import Path
import shutil

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.assets import Asset

from backend.app.schemas.assets import (
    AssetConfirm,
    AssetCreate,
    AssetResponse,
    AssetUpdate,
)

from backend.app.services.ocr_service import (
    extract_text_from_image
)

from backend.app.services.extraction_service import (
    extract_asset_fields
)


router = APIRouter(
    prefix="/assets",
    tags=["Assets"]
)


# ============================================================
# UPLOAD DIRECTORY
# ============================================================

UPLOAD_DIR = Path("uploads")

UPLOAD_DIR.mkdir(
    exist_ok=True
)


# ============================================================
# WARRANTY EXPIRY CALCULATOR
# ============================================================

def calculate_warranty_expiry(
    purchase_date: date | None,
    warranty_months: int | None
) -> date | None:
    """
    Calculate warranty expiry from:
    purchase date + warranty duration.
    """

    if purchase_date is None:
        return None

    if warranty_months is None:
        return None

    total_months = (
        purchase_date.year * 12
        + purchase_date.month
        - 1
        + warranty_months
    )

    expiry_year = total_months // 12

    expiry_month = (
        total_months % 12
    ) + 1

    last_day = monthrange(
        expiry_year,
        expiry_month
    )[1]

    expiry_day = min(
        purchase_date.day,
        last_day
    )

    return date(
        expiry_year,
        expiry_month,
        expiry_day
    )


# ============================================================
# CREATE ASSET DIRECTLY
# ============================================================

@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED
)
def create_asset(
    asset_data: AssetCreate,
    db: Session = Depends(get_db)
):
    """
    Create an asset directly using structured data.
    """

    warranty_expiry = calculate_warranty_expiry(
        asset_data.purchase_date,
        asset_data.warranty_months
    )

    asset = Asset(
        product_name=asset_data.product_name,
        brand=asset_data.brand,
        model_number=asset_data.model_number,
        serial_number=asset_data.serial_number,
        purchase_date=asset_data.purchase_date,
        purchase_price=asset_data.purchase_price,
        currency=asset_data.currency,
        warranty_months=asset_data.warranty_months,
        warranty_expiry=warranty_expiry,
        seller=asset_data.seller,
        invoice_number=asset_data.invoice_number,
    )

    db.add(asset)

    db.commit()

    db.refresh(asset)

    return asset


# ============================================================
# CONFIRM OCR DATA AND SAVE ASSET
# ============================================================

@router.post(
    "/confirm",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED
)
def confirm_asset(
    asset_data: AssetConfirm,
    db: Session = Depends(get_db)
):
    """
    Save OCR-extracted asset information only after
    the user has reviewed and confirmed it.
    """

    warranty_expiry = calculate_warranty_expiry(
        asset_data.purchase_date,
        asset_data.warranty_months
    )

    asset = Asset(
        product_name=asset_data.product_name,
        brand=asset_data.brand,
        model_number=asset_data.model_number,
        serial_number=asset_data.serial_number,
        purchase_date=asset_data.purchase_date,
        purchase_price=asset_data.purchase_price,
        currency=asset_data.currency,
        warranty_months=asset_data.warranty_months,
        warranty_expiry=warranty_expiry,
        seller=asset_data.seller,
        invoice_number=asset_data.invoice_number,
        receipt_path=asset_data.receipt_path,
    )

    db.add(asset)

    db.commit()

    db.refresh(asset)

    return asset


# ============================================================
# GET ALL ASSETS
# ============================================================

@router.get(
    "",
    response_model=list[AssetResponse]
)
def get_assets(
    db: Session = Depends(get_db)
):
    """
    Return all assets stored in the vault.
    """

    assets = (
        db.query(Asset)
        .order_by(Asset.id.desc())
        .all()
    )

    return assets


# ============================================================
# RECEIPT FILE HELPER
# ============================================================

def get_receipt_file(
    asset: Asset
) -> Path:
    """
    Safely resolve the receipt file belonging to an asset.
    """

    if not asset.receipt_path:
        raise HTTPException(
            status_code=404,
            detail="No receipt is attached to this asset."
        )

    receipt_path = Path(asset.receipt_path)

    # If the database contains something like:
    # uploads/invoice.jpg
    #
    # convert it into a path relative to the project.
    if not receipt_path.is_absolute():
        receipt_path = Path(
            receipt_path
        )

    receipt_path = receipt_path.resolve()

    upload_directory = UPLOAD_DIR.resolve()

    # Prevent access to files outside uploads/.
    try:
        receipt_path.relative_to(
            upload_directory
        )
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Invalid receipt location."
        )

    if not receipt_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Receipt file not found."
        )

    if not receipt_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Receipt file is not valid."
        )

    return receipt_path


# ============================================================
# VIEW RECEIPT
# ============================================================

@router.get(
    "/{asset_id}/receipt"
)
def view_receipt(
    asset_id: int,
    db: Session = Depends(get_db)
):
    """
    Open an asset's receipt in the browser.
    """

    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id)
        .first()
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found."
        )

    receipt_path = get_receipt_file(
        asset
    )

    return FileResponse(
        path=receipt_path,
        media_type=None,
        filename=receipt_path.name,
        content_disposition_type="inline"
    )


# ============================================================
# DOWNLOAD RECEIPT
# ============================================================

@router.get(
    "/{asset_id}/receipt/download"
)
def download_receipt(
    asset_id: int,
    db: Session = Depends(get_db)
):
    """
    Download an asset's receipt.
    """

    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id)
        .first()
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found."
        )

    receipt_path = get_receipt_file(
        asset
    )

    return FileResponse(
        path=receipt_path,
        media_type=None,
        filename=receipt_path.name,
        content_disposition_type="attachment"
    )


# ============================================================
# GET SINGLE ASSET
# ============================================================

@router.get(
    "/{asset_id}",
    response_model=AssetResponse
)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db)
):
    """
    Return one asset by ID.
    """

    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id)
        .first()
    )

    if asset is None:

        raise HTTPException(
            status_code=404,
            detail="Asset not found."
        )

    return asset


# ============================================================
# UPDATE ASSET
# ============================================================

@router.patch(
    "/{asset_id}",
    response_model=AssetResponse
)
def update_asset(
    asset_id: int,
    asset_data: AssetUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing asset.
    """

    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id)
        .first()
    )

    if asset is None:

        raise HTTPException(
            status_code=404,
            detail="Asset not found."
        )

    update_data = asset_data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():

        setattr(
            asset,
            field,
            value
        )

    asset.warranty_expiry = calculate_warranty_expiry(
        asset.purchase_date,
        asset.warranty_months
    )

    db.commit()

    db.refresh(asset)

    return asset


# ============================================================
# DELETE ASSET
# ============================================================

@router.delete(
    "/{asset_id}"
)
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete an asset from the vault.
    """

    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id)
        .first()
    )

    if asset is None:

        raise HTTPException(
            status_code=404,
            detail="Asset not found."
        )

    db.delete(asset)

    db.commit()

    return {
        "message": "Asset deleted successfully.",
        "asset_id": asset_id
    }


# ============================================================
# UPLOAD RECEIPT / INVOICE
# ============================================================

@router.post(
    "/upload-receipt"
)
async def upload_receipt(
    file: UploadFile = File(...)
):
    """
    Upload an invoice/receipt image,
    run OCR, and extract structured fields.
    """

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png"
    }

    original_filename = file.filename or ""

    file_extension = (
        Path(original_filename)
        .suffix
        .lower()
    )

    if file_extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG and PNG "
                "files are supported."
            )
        )

    filename = Path(
        original_filename
    ).name

    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    extracted_text = extract_text_from_image(
        str(file_path)
    )

    # --------------------------------------------------------
    # STRUCTURED EXTRACTION
    # --------------------------------------------------------

    extracted_fields = extract_asset_fields(
        extracted_text
    )

    # --------------------------------------------------------
    # RETURN REVIEW DATA
    # --------------------------------------------------------

    return {
        "filename": filename,

        "file_path": str(file_path),

        "extracted_text": extracted_text,

        "extracted_fields": extracted_fields
    }