"""Client Management router — clients, contracts, sales pipeline."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.client import (
    Client, ClientContract, SalesPipeline,
    ClientType, ClientStatus, ClientContractStatus, PipelineStage, BillingFrequency,
)

router = APIRouter(prefix="/api/clients", tags=["clients"])


# ── Schemas ────────────────────────────────────────────────────────
class ClientCreate(BaseModel):
    name: str
    client_type: Optional[str] = "insurance_company"
    status: Optional[str] = "prospect"
    country: Optional[str] = None
    operating_countries: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None
    primary_contact_email: Optional[str] = None
    claims_contact_name: Optional[str] = None
    claims_contact_phone: Optional[str] = None
    claims_contact_email: Optional[str] = None
    finance_contact_name: Optional[str] = None
    finance_contact_email: Optional[str] = None
    account_manager_id: Optional[str] = None
    annual_case_volume_target: Optional[int] = None
    annual_revenue_target_usd: Optional[float] = None
    client_since: Optional[str] = None
    notes: Optional[str] = None

class ClientUpdate(ClientCreate):
    name: Optional[str] = None

class ContractCreate(BaseModel):
    status: Optional[str] = "draft"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    auto_renewal: Optional[bool] = False
    billing_frequency: Optional[str] = "per_case"
    payment_terms_days: Optional[int] = 30
    billing_currency: Optional[str] = "USD"
    management_fee_type: Optional[str] = None
    management_fee_value: Optional[float] = None
    max_reimbursement_notes: Optional[str] = None
    service_scope: Optional[str] = None
    sla_commitments: Optional[str] = None
    exclusions: Optional[str] = None
    reporting_schedule: Optional[str] = None
    document_url: Optional[str] = None

class PipelineCreate(BaseModel):
    title: str
    stage: Optional[str] = "lead"
    description: Optional[str] = None
    value_usd: Optional[float] = None
    probability: Optional[int] = None
    expected_close: Optional[str] = None
    owner_id: Optional[str] = None

class PipelineUpdate(PipelineCreate):
    title: Optional[str] = None
    stage: Optional[str] = None
    lost_reason: Optional[str] = None


def _client_dict(c: Client) -> dict:
    return {
        "id": c.id, "name": c.name,
        "client_type": c.client_type.value if c.client_type else None,
        "status": c.status.value if c.status else None,
        "country": c.country,
        "operating_countries": c.operating_countries,
        "primary_contact_name": c.primary_contact_name,
        "primary_contact_phone": c.primary_contact_phone,
        "primary_contact_email": c.primary_contact_email,
        "claims_contact_name": c.claims_contact_name,
        "claims_contact_phone": c.claims_contact_phone,
        "claims_contact_email": c.claims_contact_email,
        "finance_contact_name": c.finance_contact_name,
        "finance_contact_email": c.finance_contact_email,
        "account_manager_id": c.account_manager_id,
        "account_manager_name": c.account_manager.full_name if c.account_manager else None,
        "annual_case_volume_target": c.annual_case_volume_target,
        "annual_revenue_target_usd": c.annual_revenue_target_usd,
        "client_since": c.client_since.isoformat() if c.client_since else None,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _contract_dict(c: ClientContract) -> dict:
    return {
        "id": c.id, "client_id": c.client_id,
        "contract_number": c.contract_number,
        "status": c.status.value if c.status else None,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "auto_renewal": c.auto_renewal,
        "billing_frequency": c.billing_frequency.value if c.billing_frequency else None,
        "payment_terms_days": c.payment_terms_days,
        "billing_currency": c.billing_currency,
        "management_fee_type": c.management_fee_type,
        "management_fee_value": c.management_fee_value,
        "max_reimbursement_notes": c.max_reimbursement_notes,
        "service_scope": c.service_scope,
        "sla_commitments": c.sla_commitments,
        "exclusions": c.exclusions,
        "reporting_schedule": c.reporting_schedule,
        "document_url": c.document_url,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _pipeline_dict(p: SalesPipeline) -> dict:
    return {
        "id": p.id, "client_id": p.client_id,
        "title": p.title,
        "stage": p.stage.value if p.stage else None,
        "description": p.description,
        "value_usd": p.value_usd,
        "probability": p.probability,
        "expected_close": p.expected_close.isoformat() if p.expected_close else None,
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        "lost_reason": p.lost_reason,
        "owner_id": p.owner_id,
        "owner_name": p.owner.full_name if p.owner else None,
        "client_name": p.client.name if p.client else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _next_contract_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    count = db.query(ClientContract).count()
    return f"CON-{year}-{count + 1:04d}"


# ── Client CRUD ────────────────────────────────────────────────────
@router.get("")
def list_clients(
    q: Optional[str] = None,
    client_type: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Client).options(joinedload(Client.account_manager))
    if q:
        query = query.filter(or_(
            Client.name.ilike(f"%{q}%"),
            Client.country.ilike(f"%{q}%"),
        ))
    if client_type:
        query = query.filter(Client.client_type == client_type)
    if status_filter:
        query = query.filter(Client.status == status_filter)
    total = query.count()
    clients = query.offset(skip).limit(limit).all()
    return {"total": total, "items": [_client_dict(c) for c in clients]}


@router.post("")
def create_client(
    body: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = Client()
    for field, val in body.model_dump(exclude_none=True).items():
        if field == "client_since" and val:
            c.client_since = datetime.fromisoformat(val)
        elif hasattr(c, field):
            setattr(c, field, val)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _client_dict(c)


@router.get("/pipeline")
def get_full_pipeline(
    stage: Optional[str] = None,
    owner_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SalesPipeline).options(
        joinedload(SalesPipeline.client),
        joinedload(SalesPipeline.owner),
    )
    if stage:
        q = q.filter(SalesPipeline.stage == stage)
    if owner_id:
        q = q.filter(SalesPipeline.owner_id == owner_id)
    items = q.order_by(SalesPipeline.created_at.desc()).all()
    # Group by stage
    stages = {}
    for item in items:
        s = item.stage.value if item.stage else "lead"
        stages.setdefault(s, []).append(_pipeline_dict(item))
    return {"items": [_pipeline_dict(i) for i in items], "by_stage": stages}


@router.get("/stats")
def client_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = db.query(Client).count()
    active = db.query(Client).filter(Client.status == "active").count()
    prospects = db.query(Client).filter(Client.status == "prospect").count()
    active_contracts = db.query(ClientContract).filter(
        ClientContract.status == "active"
    ).count()
    pipeline_open = db.query(SalesPipeline).filter(
        SalesPipeline.stage.notin_(["won", "lost"])
    ).count()
    pipeline_value = db.query(func.sum(SalesPipeline.value_usd)).filter(
        SalesPipeline.stage.notin_(["won", "lost"])
    ).scalar() or 0
    return {
        "total_clients": total,
        "active_clients": active,
        "prospects": prospects,
        "active_contracts": active_contracts,
        "pipeline_open_count": pipeline_open,
        "pipeline_open_value_usd": round(pipeline_value, 2),
    }


@router.get("/{client_id}")
def get_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = db.query(Client).options(
        joinedload(Client.account_manager),
        joinedload(Client.contracts),
        joinedload(Client.pipeline_items),
    ).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    result = _client_dict(c)
    result["contracts"] = [_contract_dict(ct) for ct in c.contracts]
    result["pipeline"] = [_pipeline_dict(p) for p in c.pipeline_items]
    return result


@router.patch("/{client_id}")
def update_client(
    client_id: str,
    body: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, val in body.model_dump(exclude_none=True).items():
        if field == "client_since" and val:
            c.client_since = datetime.fromisoformat(val)
        elif hasattr(c, field):
            setattr(c, field, val)
    db.commit()
    db.refresh(c)
    return _client_dict(c)


# ── Contracts ──────────────────────────────────────────────────────
@router.post("/{client_id}/contracts")
def create_client_contract(
    client_id: str,
    body: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    c = ClientContract(
        client_id=client_id,
        contract_number=_next_contract_number(db),
        created_by=current_user.id,
    )
    for field, val in body.model_dump(exclude_none=True).items():
        if field in ("start_date", "end_date") and val:
            setattr(c, field, datetime.fromisoformat(val))
        elif hasattr(c, field):
            setattr(c, field, val)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _contract_dict(c)


@router.patch("/{client_id}/contracts/{contract_id}")
def update_client_contract(
    client_id: str, contract_id: str,
    body: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = db.query(ClientContract).filter(
        ClientContract.id == contract_id,
        ClientContract.client_id == client_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    for field, val in body.model_dump(exclude_none=True).items():
        if field in ("start_date", "end_date") and val:
            setattr(c, field, datetime.fromisoformat(val))
        elif hasattr(c, field):
            setattr(c, field, val)
    db.commit()
    db.refresh(c)
    return _contract_dict(c)


# ── Pipeline ───────────────────────────────────────────────────────
@router.post("/{client_id}/pipeline")
def create_pipeline_item(
    client_id: str,
    body: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    p = SalesPipeline(client_id=client_id, owner_id=current_user.id)
    for field, val in body.model_dump(exclude_none=True).items():
        if field == "expected_close" and val:
            p.expected_close = datetime.fromisoformat(val)
        elif hasattr(p, field):
            setattr(p, field, val)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _pipeline_dict(p)


@router.patch("/{client_id}/pipeline/{item_id}")
def update_pipeline_item(
    client_id: str, item_id: str,
    body: PipelineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.query(SalesPipeline).filter(
        SalesPipeline.id == item_id,
        SalesPipeline.client_id == client_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline item not found")
    data = body.model_dump(exclude_none=True)
    if "stage" in data and data["stage"] in ("won", "lost"):
        p.closed_at = datetime.now(timezone.utc)
    for field, val in data.items():
        if field == "expected_close" and val:
            p.expected_close = datetime.fromisoformat(val)
        elif hasattr(p, field):
            setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return _pipeline_dict(p)
