import json
import secrets
from typing import Optional, Dict, Any, Union

from sqlalchemy.orm import Session

from .models import Trip, TripItem, TripParticipant
from .schemas import TripCreate, ItemCreate, ParticipantCreate


def cents_to_money(cents: int) -> str:
    # 123456 -> "1,234.56"
    return f"{cents/100:,.2f}"


def meta_from_json(meta_json: Optional[str]) -> Dict[str, Any]:
    if not meta_json:
        return {}
    try:
        return json.loads(meta_json)
    except Exception:
        return {}


def create_trip(db: Session, payload: TripCreate) -> Trip:
    token = secrets.token_hex(16)
    trip = Trip(
        token=token,
        title=payload.title.strip(),
        destination=payload.destination.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        currency=(payload.currency or "BRL").strip().upper(),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def get_trip_by_token(db: Session, token: str) -> Optional[Trip]:
    return db.query(Trip).filter(Trip.token == token).first()


def _normalize_cost_to_cents(cost: Union[int, float, str, None]) -> Optional[int]:
    """
    Aceita:
      - int: já em centavos (ex: 12345)
      - float/str: valor (ex: 123.45) -> vira centavos
    """
    if cost is None:
        return None

    # int -> assume centavos (se vier 1200, é R$12,00)
    if isinstance(cost, int):
        return cost

    # float/str -> assume valor em moeda
    try:
        f = float(cost)
        return int(round(f * 100))
    except Exception:
        return None


def create_item(db: Session, trip: Trip, payload: ItemCreate) -> TripItem:
    cost_cents = _normalize_cost_to_cents(payload.cost)

    meta_json = None
    if payload.meta:
        meta_json = json.dumps(payload.meta, ensure_ascii=False)

    item = TripItem(
        trip_id=trip.id,
        category=payload.category,
        title=payload.title.strip(),
        item_date=payload.item_date,
        url=payload.url.strip() if payload.url else None,
        notes=payload.notes if payload.notes else None,
        cost=cost_cents,
        meta_json=meta_json,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, trip: Trip, item_id: int) -> bool:
    item = db.query(TripItem).filter(TripItem.trip_id == trip.id, TripItem.id == item_id).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def add_participant(db: Session, trip: Trip, payload: ParticipantCreate) -> TripParticipant:
    name = payload.name.strip()
    email = payload.email.strip().lower() if payload.email else None

    if email:
        existing = (
            db.query(TripParticipant)
            .filter(TripParticipant.trip_id == trip.id, TripParticipant.email == email)
            .first()
        )
        if existing:
            if existing.name != name:
                existing.name = name
                db.commit()
                db.refresh(existing)
            return existing

    p = TripParticipant(trip_id=trip.id, name=name, email=email)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def remove_participant(db: Session, trip: Trip, participant_id: int) -> bool:
    p = (
        db.query(TripParticipant)
        .filter(TripParticipant.trip_id == trip.id, TripParticipant.id == participant_id)
        .first()
    )
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True
