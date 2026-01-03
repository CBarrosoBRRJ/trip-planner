from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
from pathlib import Path

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .db import Base, engine, get_db, ensure_db_ready
from .schemas import TripCreate, ItemCreate, ParticipantCreate
from .services import (
    create_trip,
    get_trip_by_token,
    create_item,
    delete_item,
    add_participant,
    remove_participant,
    cents_to_money,
    meta_from_json,
)

# === paths robustos (local + deploy) ===
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

# cria tabelas (MVP)
ensure_db_ready()

app = FastAPI(title="Trip Planner")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

CATEGORY_LABEL = {
    "activity": "Passeios",
    "restaurant": "Restaurantes",
    "hotel": "Hospedagens",
    "flight": "Passagens",
    "transport": "Transporte",
    "ticket": "Tickets",
    "reference": "Links",
    "notes": "Anotações",
}

def parse_yyyy_mm_dd(value: str, field: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Data inválida em {field}. Use YYYY-MM-DD.")

def parse_money_to_float(value: str):
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    s = s.replace(" ", "")
    if any(c.isalpha() for c in s):
        raise ValueError("Valor inválido. Use apenas números (ex: 120 ou 120,50).")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "")
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        if "," in s:
            s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        raise ValueError("Valor inválido. Use apenas números (ex: 120 ou 120,50).")

def build_google_calendar_link(title: str, destination: str, start_date, end_date, details_url: str):
    dates = f"{start_date.strftime('%Y%m%d')}/{end_date.strftime('%Y%m%d')}"
    params = {
        "action": "TEMPLATE",
        "text": f"{title} - {destination}",
        "dates": dates,
        "details": f"Planejamento: {details_url}",
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)

def redirect_with_error(token: str, msg: str):
    return RedirectResponse(url=f"/t/{token}?error={quote(msg)}", status_code=303)

def enforce_date_in_trip(trip, dt, label: str):
    if dt is None:
        return
    if dt < trip.start_date or dt > trip.end_date:
        raise HTTPException(
            status_code=400,
            detail=f"{label} fora do período da viagem ({trip.start_date} → {trip.end_date}).",
        )

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/t/new", status_code=302)

@app.get("/t/new", response_class=HTMLResponse)
def trip_new_page(request: Request):
    return templates.TemplateResponse(
        "trip_onepage.html",
        {
            "request": request,
            "mode": "create",
            "trip": None,
            "share_url": None,
            "gcal_url": None,
            "groups": {},
            "by_day": {},
            "days_sorted": [],
            "participants": [],
            "category_label": CATEGORY_LABEL,
            "cents_to_money": cents_to_money,
            "total_by_cat": {},
            "total_all": 0,
            "per_person": 0,
            "error": None,
        },
    )

@app.post("/t/new")
def trip_create_submit(
    request: Request,
    title: str = Form(...),
    destination: str = Form(...),
    start_date: str = Form(...),
    duration_days: str = Form(""),
    end_date: str = Form(""),
    currency: str = Form("BRL"),
    db: Session = Depends(get_db),
):
    try:
        start_dt = parse_yyyy_mm_dd(start_date, "Início")

        end_dt = None
        if end_date and end_date.strip():
            end_dt = parse_yyyy_mm_dd(end_date, "Fim")
        else:
            if duration_days and duration_days.strip():
                d = int(duration_days.strip())
                if d <= 0 or d > 365:
                    raise HTTPException(status_code=400, detail="Duração inválida (use 1 a 365 dias).")
                end_dt = start_dt + timedelta(days=d - 1)
            else:
                raise HTTPException(status_code=400, detail="Informe o fim ou a duração da viagem.")

        if end_dt < start_dt:
            raise HTTPException(status_code=400, detail="Fim não pode ser antes do início.")

        payload = TripCreate(
            title=title,
            destination=destination,
            start_date=start_dt,
            end_date=end_dt,
            currency=currency,
        )
        trip = create_trip(db, payload)
        return RedirectResponse(url=f"/t/{trip.token}", status_code=303)

    except HTTPException as e:
        return templates.TemplateResponse(
            "trip_onepage.html",
            {
                "request": request,
                "mode": "create",
                "trip": None,
                "share_url": None,
                "gcal_url": None,
                "groups": {},
                "by_day": {},
                "days_sorted": [],
                "participants": [],
                "category_label": CATEGORY_LABEL,
                "cents_to_money": cents_to_money,
                "total_by_cat": {},
                "total_all": 0,
                "per_person": 0,
                "error": e.detail,
            },
            status_code=e.status_code,
        )

@app.get("/t/{token}", response_class=HTMLResponse)
def trip_page(token: str, request: Request, db: Session = Depends(get_db)):
    trip = get_trip_by_token(db, token)
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")

    base = str(request.base_url).rstrip("/")
    share_url = f"{base}/t/{trip.token}"
    gcal_url = build_google_calendar_link(trip.title, trip.destination, trip.start_date, trip.end_date, share_url)
    error = request.query_params.get("error")

    groups = defaultdict(list)
    total_by_cat = defaultdict(int)
    total_all = 0

    for item in trip.items:
        meta = meta_from_json(getattr(item, "meta_json", None))
        item._meta = meta
        groups[item.category].append(item)

        if item.cost is not None:
            total_by_cat[item.category] += item.cost
            total_all += item.cost

    for cat in list(groups.keys()):
        groups[cat].sort(key=lambda x: (x.item_date is None, x.item_date, x.created_at))

    by_day = defaultdict(list)
    for it in groups.get("activity", []):
        if it.item_date:
            by_day[it.item_date].append(it)
    for d in list(by_day.keys()):
        by_day[d].sort(key=lambda x: (x._meta.get("time", ""), x.created_at))
    days_sorted = sorted(by_day.keys())

    participants = sorted(trip.participants, key=lambda p: p.created_at)
    people = max(1, len(participants))
    per_person = int(round(total_all / people)) if total_all else 0

    return templates.TemplateResponse(
        "trip_onepage.html",
        {
            "request": request,
            "mode": "view",
            "trip": trip,
            "share_url": share_url,
            "gcal_url": gcal_url,
            "groups": groups,
            "by_day": by_day,
            "days_sorted": days_sorted,
            "participants": participants,
            "category_label": CATEGORY_LABEL,
            "cents_to_money": cents_to_money,
            "total_by_cat": total_by_cat,
            "total_all": total_all,
            "per_person": per_person,
            "error": error,
        },
    )

@app.post("/t/{token}/edit")
def edit_trip(
    token: str,
    title: str = Form(...),
    destination: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    currency: str = Form("BRL"),
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(db, token)
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")

    try:
        sd = parse_yyyy_mm_dd(start_date, "Início")
        ed = parse_yyyy_mm_dd(end_date, "Fim")
        if ed < sd:
            return redirect_with_error(token, "Fim não pode ser antes do início.")
        trip.title = title.strip()
        trip.destination = destination.strip()
        trip.start_date = sd
        trip.end_date = ed
        trip.currency = (currency or "BRL").strip().upper()
        db.commit()
        return RedirectResponse(url=f"/t/{token}", status_code=303)
    except HTTPException as e:
        return redirect_with_error(token, str(e.detail))

@app.post("/t/{token}/join")
def join_trip(token: str, name: str = Form(...), email: str = Form(""), db: Session = Depends(get_db)):
    trip = get_trip_by_token(db, token)
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")
    payload = ParticipantCreate(name=name, email=email or None)
    add_participant(db, trip, payload)
    return RedirectResponse(url=f"/t/{token}", status_code=303)

@app.post("/t/{token}/participants/{participant_id}/delete")
def delete_participant(token: str, participant_id: int, db: Session = Depends(get_db)):
    trip = get_trip_by_token(db, token)
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")
    remove_participant(db, trip, participant_id)
    return RedirectResponse(url=f"/t/{token}", status_code=303)

@app.post("/t/{token}/items")
def add_item(
    token: str,
    category: str = Form(...),

    title: str = Form(""),
    item_date: str = Form(""),
    url: str = Form(""),
    cost: str = Form(""),

    place: str = Form(""),
    address: str = Form(""),
    time_str: str = Form(""),

    needs_ticket: str = Form(""),
    ticket_url: str = Form(""),
    ticket_cost: str = Form(""),
    needs_transport: str = Form(""),
    transport_url: str = Form(""),
    transport_cost: str = Form(""),
    uber_flag: str = Form(""),
    walk_flag: str = Form(""),
    notes: str = Form(""),

    origin: str = Form(""),
    destination: str = Form(""),
    flight_duration: str = Form(""),
    has_connection: str = Form(""),
    connection_place: str = Form(""),
    connection_duration: str = Form(""),
    company: str = Form(""),

    nights: str = Form(""),
    daily_value: str = Form(""),

    transport_type: str = Form(""),
    transport_duration: str = Form(""),
    transport_link: str = Form(""),
    is_car_rental: str = Form(""),
    car_daily: str = Form(""),
    car_days: str = Form(""),

    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(db, token)
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")

    parsed_item_date = None
    if item_date.strip():
        try:
            parsed_item_date = parse_yyyy_mm_dd(item_date.strip(), "Data")
            enforce_date_in_trip(trip, parsed_item_date, "Data")
        except HTTPException as e:
            return redirect_with_error(token, str(e.detail))

    parsed_cost = None
    if cost.strip():
        try:
            parsed_cost = parse_money_to_float(cost)
        except ValueError as ve:
            return redirect_with_error(token, str(ve))

    meta = {}

    # comuns
    if address.strip():
        meta["address"] = address.strip()
    if time_str.strip():
        meta["time"] = time_str.strip()
    if notes.strip():
        meta["notes"] = notes.strip()

    # activity (passeios)
    if category == "activity":
        meta["needs_ticket"] = bool(needs_ticket)
        if ticket_url.strip():
            meta["ticket_url"] = ticket_url.strip()
        if ticket_cost.strip():
            try:
                meta["ticket_cost"] = parse_money_to_float(ticket_cost)
            except ValueError as ve:
                return redirect_with_error(token, f"Ingresso: {ve}")
        meta["needs_transport"] = bool(needs_transport)
        if transport_url.strip():
            meta["transport_url"] = transport_url.strip()
        if transport_cost.strip():
            try:
                meta["transport_cost"] = parse_money_to_float(transport_cost)
            except ValueError as ve:
                return redirect_with_error(token, f"Transporte: {ve}")
        meta["uber"] = bool(uber_flag)
        meta["walk"] = bool(walk_flag)

    # flight
    if category == "flight":
        if origin.strip():
            meta["origin"] = origin.strip()
        if destination.strip():
            meta["destination"] = destination.strip()
        if company.strip():
            meta["company"] = company.strip()
        if flight_duration.strip():
            meta["duration"] = flight_duration.strip()
        meta["has_connection"] = bool(has_connection)
        if connection_place.strip():
            meta["connection_place"] = connection_place.strip()
        if connection_duration.strip():
            meta["connection_duration"] = connection_duration.strip()

    # hotel
    if category == "hotel":
        if nights.strip():
            meta["nights"] = nights.strip()
        if daily_value.strip():
            meta["daily_value"] = daily_value.strip()

    # transport
    if category == "transport":
        if transport_type.strip():
            meta["transport_type"] = transport_type.strip()
        if transport_duration.strip():
            meta["duration"] = transport_duration.strip()
        if transport_link.strip():
            meta["ticket_url"] = transport_link.strip()
        meta["is_car_rental"] = bool(is_car_rental)
        if car_daily.strip():
            meta["car_daily"] = car_daily.strip()
        if car_days.strip():
            meta["car_days"] = car_days.strip()

        # se for aluguel, custo pode ser calculado (car_daily * car_days) se custo vazio
        if (not parsed_cost) and car_daily.strip() and car_days.strip():
            try:
                cd = parse_money_to_float(car_daily)
                nd = int(car_days.strip())
                if cd is not None and nd > 0:
                    parsed_cost = cd * nd
            except Exception:
                pass

    final_title = title.strip()
    if not final_title:
        if category == "activity":
            final_title = (place.strip() or "Passeio")
        elif category == "restaurant":
            final_title = (place.strip() or "Restaurante")
        elif category == "hotel":
            final_title = (place.strip() or "Hospedagem")
        elif category == "flight":
            if origin.strip() or destination.strip():
                final_title = f"{origin.strip()} → {destination.strip()}".strip(" →")
            else:
                final_title = "Voo"
        elif category == "transport":
            final_title = transport_type.strip() or "Transporte"
        else:
            final_title = "Item"

    try:
        payload = ItemCreate(
            category=category,
            title=final_title,
            item_date=parsed_item_date,
            url=url.strip() or None,
            cost=parsed_cost,
            notes=None,
            meta=meta or None,
        )
        create_item(db, trip, payload)
        return RedirectResponse(url=f"/t/{token}", status_code=303)
    except Exception:
        return redirect_with_error(token, "Erro ao salvar item. Verifique os campos e tente novamente.")

@app.post("/t/{token}/items/{item_id}/delete")
def remove_item(token: str, item_id: int, db: Session = Depends(get_db)):
    trip = get_trip_by_token(db, token)
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")
    delete_item(db, trip, item_id)
    return RedirectResponse(url=f"/t/{token}", status_code=303)

@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})
