"""Finance router — invoices, payments, revenue summaries."""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.auth import get_current_user
from app.models.user import User, UserRole
from app.models.finance import Invoice, InvoiceItem, Payment, InvoiceStatus, PaymentMethod
from app.models.patient import Patient
from app.models.case import Case

router = APIRouter(prefix="/api/finance", tags=["finance"])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _next_invoice_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"INV-{year}-"
    last = (
        db.query(Invoice.invoice_number)
        .filter(Invoice.invoice_number.like(f"{prefix}%"))
        .order_by(Invoice.invoice_number.desc())
        .first()
    )
    if last:
        try:
            seq = int(last[0].split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


def _invoice_to_dict(inv: Invoice, include_items: bool = True) -> dict:
    d = {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "case_id": inv.case_id,
        "patient_id": inv.patient_id,
        "patient_name": inv.patient.name if inv.patient else None,
        "issued_to_name": inv.issued_to_name,
        "issued_to_email": inv.issued_to_email,
        "subtotal": inv.subtotal,
        "tax_amount": inv.tax_amount,
        "discount_amount": inv.discount_amount,
        "total_amount": inv.total_amount,
        "paid_amount": inv.paid_amount,
        "balance_due": round(inv.total_amount - inv.paid_amount, 2),
        "currency": inv.currency,
        "status": inv.status,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "notes": inv.notes,
        "created_by": inv.created_by,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
    }
    if include_items:
        d["items"] = [_item_to_dict(i) for i in (inv.items or [])]
        d["payments"] = [_payment_to_dict(p) for p in (inv.payments or [])]
    return d


def _item_to_dict(item: InvoiceItem) -> dict:
    return {
        "id": item.id,
        "invoice_id": item.invoice_id,
        "description": item.description,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "total": item.total,
    }


def _payment_to_dict(p: Payment) -> dict:
    return {
        "id": p.id,
        "invoice_id": p.invoice_id,
        "amount": p.amount,
        "currency": p.currency,
        "method": p.method,
        "reference_number": p.reference_number,
        "notes": p.notes,
        "received_by": p.received_by,
        "receiver_name": p.receiver.full_name if p.receiver else None,
        "received_at": p.received_at.isoformat() if p.received_at else None,
    }


def _recalculate_invoice(inv: Invoice, db: Session):
    """Recalculate subtotal/total from items and paid_amount from payments."""
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).all()
    inv.subtotal = round(sum(i.total for i in items), 2)
    inv.total_amount = round(inv.subtotal + inv.tax_amount - inv.discount_amount, 2)

    payments = db.query(Payment).filter(Payment.invoice_id == inv.id).all()
    inv.paid_amount = round(sum(p.amount for p in payments), 2)

    # Auto-update status
    if inv.total_amount <= 0:
        return
    if inv.paid_amount <= 0:
        if inv.status not in (InvoiceStatus.draft, InvoiceStatus.void):
            pass  # keep existing status
    elif inv.paid_amount >= inv.total_amount:
        inv.status = InvoiceStatus.paid
        if not inv.paid_at:
            inv.paid_at = datetime.now(timezone.utc)
    else:
        inv.status = InvoiceStatus.partial


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ItemSchema(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float


class InvoiceCreate(BaseModel):
    patient_id: str
    case_id: Optional[str] = None
    issued_to_name: Optional[str] = None
    issued_to_email: Optional[str] = None
    currency: Optional[str] = "USD"
    tax_amount: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    items: List[ItemSchema] = []


class InvoiceUpdate(BaseModel):
    issued_to_name: Optional[str] = None
    issued_to_email: Optional[str] = None
    currency: Optional[str] = None
    tax_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[InvoiceStatus] = None


class PaymentCreate(BaseModel):
    amount: float
    currency: Optional[str] = None  # defaults to invoice currency
    method: PaymentMethod = PaymentMethod.cash
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    received_at: Optional[datetime] = None


# ─── Invoice routes ───────────────────────────────────────────────────────────

@router.get("/invoices")
def list_invoices(
    patient_id: Optional[str] = Query(None),
    case_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Invoice).options(joinedload(Invoice.patient))
    if patient_id:
        q = q.filter(Invoice.patient_id == patient_id)
    if case_id:
        q = q.filter(Invoice.case_id == case_id)
    if status:
        q = q.filter(Invoice.status == status)

    total = q.count()
    invoices = q.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_invoice_to_dict(inv, include_items=False) for inv in invoices]}


@router.post("/invoices", status_code=201)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    inv = Invoice(
        invoice_number=_next_invoice_number(db),
        patient_id=payload.patient_id,
        case_id=payload.case_id,
        issued_to_name=payload.issued_to_name or patient.name,
        issued_to_email=payload.issued_to_email or patient.email,
        currency=payload.currency or "USD",
        tax_amount=payload.tax_amount or 0.0,
        discount_amount=payload.discount_amount or 0.0,
        subtotal=0.0,
        total_amount=0.0,
        paid_amount=0.0,
        due_date=payload.due_date,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(inv)
    db.flush()

    # Add line items
    for item_data in payload.items:
        total = round(item_data.quantity * item_data.unit_price, 2)
        db.add(InvoiceItem(
            invoice_id=inv.id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            total=total,
        ))

    db.flush()
    _recalculate_invoice(inv, db)
    db.commit()
    db.refresh(inv)

    inv = (
        db.query(Invoice)
        .options(joinedload(Invoice.patient), joinedload(Invoice.items), joinedload(Invoice.payments))
        .filter(Invoice.id == inv.id)
        .first()
    )
    return _invoice_to_dict(inv)


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inv = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.patient),
            joinedload(Invoice.items),
            joinedload(Invoice.payments).joinedload(Payment.receiver),
        )
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_dict(inv)


@router.put("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == InvoiceStatus.void:
        raise HTTPException(status_code=400, detail="Cannot modify a voided invoice")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(inv, field, value)

    if payload.tax_amount is not None or payload.discount_amount is not None:
        _recalculate_invoice(inv, db)

    db.commit()
    inv = (
        db.query(Invoice)
        .options(joinedload(Invoice.patient), joinedload(Invoice.items), joinedload(Invoice.payments))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    return _invoice_to_dict(inv)


@router.post("/invoices/{invoice_id}/items", status_code=201)
def add_invoice_item(
    invoice_id: str,
    payload: ItemSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    total = round(payload.quantity * payload.unit_price, 2)
    item = InvoiceItem(
        invoice_id=invoice_id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total=total,
    )
    db.add(item)
    db.flush()
    _recalculate_invoice(inv, db)
    db.commit()
    return _item_to_dict(item)


@router.delete("/invoices/{invoice_id}/items/{item_id}")
def delete_invoice_item(
    invoice_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query(InvoiceItem).filter(InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.flush()
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    _recalculate_invoice(inv, db)
    db.commit()
    return {"deleted": item_id}


# ─── Payments ────────────────────────────────────────────────────────────────

@router.post("/invoices/{invoice_id}/payments", status_code=201)
def record_payment(
    invoice_id: str,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == InvoiceStatus.void:
        raise HTTPException(status_code=400, detail="Cannot record payment on a voided invoice")

    payment = Payment(
        invoice_id=invoice_id,
        amount=payload.amount,
        currency=payload.currency or inv.currency,
        method=payload.method,
        reference_number=payload.reference_number,
        notes=payload.notes,
        received_by=current_user.id,
        received_at=payload.received_at or datetime.now(timezone.utc),
    )
    db.add(payment)
    db.flush()
    _recalculate_invoice(inv, db)
    db.commit()
    db.refresh(payment)
    payment = db.query(Payment).options(joinedload(Payment.receiver)).filter(Payment.id == payment.id).first()
    return _payment_to_dict(payment)


@router.delete("/invoices/{invoice_id}/payments/{payment_id}")
def delete_payment(
    invoice_id: str,
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.invoice_id == invoice_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    db.delete(payment)
    db.flush()
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    _recalculate_invoice(inv, db)
    db.commit()
    return {"deleted": payment_id}


# ─── Summary ─────────────────────────────────────────────────────────────────

@router.get("/summary")
def finance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """High-level revenue summary for the dashboard."""
    total_billed = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.status != InvoiceStatus.void
    ).scalar() or 0.0

    total_collected = db.query(func.sum(Invoice.paid_amount)).filter(
        Invoice.status != InvoiceStatus.void
    ).scalar() or 0.0

    outstanding = db.query(func.sum(Invoice.total_amount - Invoice.paid_amount)).filter(
        Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.partial, InvoiceStatus.overdue])
    ).scalar() or 0.0

    counts = {}
    for status in InvoiceStatus:
        counts[status.value] = db.query(func.count(Invoice.id)).filter(Invoice.status == status).scalar() or 0

    # Monthly breakdown (last 6 months) — paid_amount by month of created_at
    from sqlalchemy import extract
    monthly = []
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        mo = (now.month - i - 1) % 12 + 1
        yr = now.year - ((i + (now.month - 1)) // 12)
        collected = db.query(func.sum(Payment.amount)).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).filter(
            extract("year", Payment.received_at) == yr,
            extract("month", Payment.received_at) == mo,
        ).scalar() or 0.0
        monthly.append({
            "year": yr,
            "month": mo,
            "label": datetime(yr, mo, 1).strftime("%b %Y"),
            "collected": round(collected, 2),
        })

    return {
        "total_billed": round(total_billed, 2),
        "total_collected": round(total_collected, 2),
        "outstanding": round(outstanding, 2),
        "by_status": counts,
        "monthly": monthly,
    }
