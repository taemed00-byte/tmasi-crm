"""Network Management router — providers (clinics), contracts, tariffs."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.clinic import Clinic
from app.models.network import (
    ProviderContract, ProviderTariff,
    ProviderCategory, ProviderType, ContractStatus,
)
from app.models.case import Case

router = APIRouter(prefix="/api/network", tags=["network"])


# ── Pydantic schemas ──────────────────────────────────────────────
class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    specialties: Optional[str] = None
    accreditations: Optional[str] = None
    languages: Optional[str] = None
    emergency_phone: Optional[str] = None
    accepted_currencies: Optional[str] = None
    bed_capacity: Optional[int] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class ContractCreate(BaseModel):
    provider_id: str
    status: Optional[str] = "draft"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    auto_renewal: Optional[bool] = False
    credit_terms_days: Optional[int] = 30
    discount_percentage: Optional[float] = 0.0
    payment_currency: Optional[str] = "USD"
    scope_notes: Optional[str] = None
    exclusions: Optional[str] = None
    document_url: Optional[str] = None

class ContractUpdate(BaseModel):
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    auto_renewal: Optional[bool] = None
    credit_terms_days: Optional[int] = None
    discount_percentage: Optional[float] = None
    payment_currency: Optional[str] = None
    scope_notes: Optional[str] = None
    exclusions: Optional[str] = None
    document_url: Optional[str] = None

class TariffCreate(BaseModel):
    service_category: str
    service_name: str
    pricing_model: Optional[str] = None
    unit_cost: float
    currency: Optional[str] = "USD"
    notes: Optional[str] = None


def _provider_dict(p: Clinic) -> dict:
    return {
        "id": p.id, "name": p.name,
        "provider_type": getattr(p, "provider_type", "clinic"),
        "category": getattr(p, "category", "standard"),
        "address": p.address, "city": p.city, "country": p.country,
        "phone": p.phone, "email": p.email,
        "specialties": p.specialties,
        "accreditations": getattr(p, "accreditations", None),
        "languages": getattr(p, "languages", None),
        "emergency_phone": getattr(p, "emergency_phone", None),
        "accepted_currencies": getattr(p, "accepted_currencies", "USD"),
        "bed_capacity": getattr(p, "bed_capacity", None),
        "gps_lat": getattr(p, "gps_lat", None),
        "gps_lng": getattr(p, "gps_lng", None),
        "notes": getattr(p, "notes", None),
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _contract_dict(c: ProviderContract) -> dict:
    return {
        "id": c.id, "provider_id": c.provider_id,
        "contract_number": c.contract_number,
        "status": c.status.value if c.status else None,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "auto_renewal": c.auto_renewal,
        "credit_terms_days": c.credit_terms_days,
        "discount_percentage": c.discount_percentage,
        "payment_currency": c.payment_currency,
        "scope_notes": c.scope_notes,
        "exclusions": c.exclusions,
        "document_url": c.document_url,
        "provider_name": c.provider.name if c.provider else None,
        "tariffs": [_tariff_dict(t) for t in c.tariffs],
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _tariff_dict(t: ProviderTariff) -> dict:
    return {
        "id": t.id, "contract_id": t.contract_id,
        "service_category": t.service_category,
        "service_name": t.service_name,
        "pricing_model": t.pricing_model,
        "unit_cost": t.unit_cost,
        "currency": t.currency,
        "notes": t.notes,
    }


def _next_contract_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    count = db.query(ProviderContract).filter(
        func.strftime("%Y", ProviderContract.created_at) == str(year)
    ).count() if "sqlite" in str(db.bind.url) else db.query(ProviderContract).filter(
        func.extract("year", ProviderContract.created_at) == year
    ).count()
    return f"PC-{year}-{count + 1:04d}"


# ── Provider endpoints ────────────────────────────────────────────
@router.get("/providers")
def list_providers(
    q: Optional[str] = None,
    category: Optional[str] = None,
    provider_type: Optional[str] = None,
    country: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Clinic)
    if q:
        query = query.filter(or_(
            Clinic.name.ilike(f"%{q}%"),
            Clinic.city.ilike(f"%{q}%"),
            Clinic.specialties.ilike(f"%{q}%"),
        ))
    if category:
        query = query.filter(Clinic.category == category)
    if provider_type:
        query = query.filter(Clinic.provider_type == provider_type)
    if country:
        query = query.filter(Clinic.country.ilike(f"%{country}%"))
    if is_active is not None:
        query = query.filter(Clinic.is_active == is_active)
    total = query.count()
    providers = query.offset(skip).limit(limit).all()
    return {"total": total, "items": [_provider_dict(p) for p in providers]}


@router.post("/providers")
def create_provider(
    body: ProviderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = Clinic(name=body.name or "New Provider")
    for field, val in body.model_dump(exclude_none=True).items():
        if hasattr(p, field):
            setattr(p, field, val)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _provider_dict(p)


@router.get("/providers/{provider_id}")
def get_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.query(Clinic).filter(Clinic.id == provider_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    result = _provider_dict(p)
    # Attach contracts and performance
    contracts = db.query(ProviderContract).filter(
        ProviderContract.provider_id == provider_id
    ).all()
    result["contracts"] = [_contract_dict(c) for c in contracts]

    # Performance KPIs
    total_cases = db.query(Case).filter(Case.clinic_id == provider_id).count()
    result["performance"] = {"total_cases": total_cases}
    return result


@router.patch("/providers/{provider_id}")
def update_provider(
    provider_id: str,
    body: ProviderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.query(Clinic).filter(Clinic.id == provider_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    for field, val in body.model_dump(exclude_none=True).items():
        if hasattr(p, field):
            setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return _provider_dict(p)


# ── Contract endpoints ────────────────────────────────────────────
@router.get("/contracts")
def list_contracts(
    provider_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy.orm import joinedload
    q = db.query(ProviderContract).options(
        joinedload(ProviderContract.provider),
        joinedload(ProviderContract.tariffs),
    )
    if provider_id:
        q = q.filter(ProviderContract.provider_id == provider_id)
    if status_filter:
        q = q.filter(ProviderContract.status == status_filter)
    contracts = q.order_by(ProviderContract.created_at.desc()).all()
    return [_contract_dict(c) for c in contracts]


@router.post("/contracts")
def create_contract(
    body: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    provider = db.query(Clinic).filter(Clinic.id == body.provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    c = ProviderContract(
        provider_id=body.provider_id,
        contract_number=_next_contract_number(db),
        status=body.status or "draft",
        auto_renewal=body.auto_renewal,
        credit_terms_days=body.credit_terms_days,
        discount_percentage=body.discount_percentage,
        payment_currency=body.payment_currency,
        scope_notes=body.scope_notes,
        exclusions=body.exclusions,
        document_url=body.document_url,
        created_by=current_user.id,
    )
    if body.start_date:
        c.start_date = datetime.fromisoformat(body.start_date)
    if body.end_date:
        c.end_date = datetime.fromisoformat(body.end_date)
    db.add(c)
    db.commit()
    db.refresh(c)
    from sqlalchemy.orm import joinedload
    c = db.query(ProviderContract).options(
        joinedload(ProviderContract.provider),
        joinedload(ProviderContract.tariffs),
    ).filter(ProviderContract.id == c.id).first()
    return _contract_dict(c)


@router.patch("/contracts/{contract_id}")
def update_contract(
    contract_id: str,
    body: ContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy.orm import joinedload
    c = db.query(ProviderContract).filter(ProviderContract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    data = body.model_dump(exclude_none=True)
    for field, val in data.items():
        if field in ("start_date", "end_date") and val:
            setattr(c, field, datetime.fromisoformat(val))
        elif hasattr(c, field):
            setattr(c, field, val)
    db.commit()
    c = db.query(ProviderContract).options(
        joinedload(ProviderContract.provider),
        joinedload(ProviderContract.tariffs),
    ).filter(ProviderContract.id == contract_id).first()
    return _contract_dict(c)


@router.post("/contracts/{contract_id}/tariffs")
def add_tariff(
    contract_id: str,
    body: TariffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = db.query(ProviderContract).filter(ProviderContract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    t = ProviderTariff(
        contract_id=contract_id,
        service_category=body.service_category,
        service_name=body.service_name,
        pricing_model=body.pricing_model,
        unit_cost=body.unit_cost,
        currency=body.currency,
        notes=body.notes,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _tariff_dict(t)


@router.delete("/contracts/{contract_id}/tariffs/{tariff_id}")
def delete_tariff(
    contract_id: str, tariff_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = db.query(ProviderTariff).filter(
        ProviderTariff.id == tariff_id,
        ProviderTariff.contract_id == contract_id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tariff not found")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.get("/stats")
def network_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = db.query(Clinic).count()
    active = db.query(Clinic).filter(Clinic.is_active == True).count()
    preferred = db.query(Clinic).filter(Clinic.category == "preferred").count()
    restricted = db.query(Clinic).filter(Clinic.category == "restricted").count()
    blacklisted = db.query(Clinic).filter(Clinic.category == "blacklisted").count()
    active_contracts = db.query(ProviderContract).filter(
        ProviderContract.status == "active"
    ).count()
    expiring_soon = db.query(ProviderContract).filter(
        ProviderContract.status == "active",
        ProviderContract.end_date <= datetime.now(timezone.utc) + timedelta(days=90),
        ProviderContract.end_date >= datetime.now(timezone.utc),
    ).count()
    return {
        "total_providers": total,
        "active_providers": active,
        "preferred": preferred,
        "restricted": restricted,
        "blacklisted": blacklisted,
        "active_contracts": active_contracts,
        "contracts_expiring_soon": expiring_soon,
    }
