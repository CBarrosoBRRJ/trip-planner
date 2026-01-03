from datetime import datetime, time, timedelta
from ics import Calendar, Event

CATEGORY_TITLE = {
    "flight": "Passagem",
    "hotel": "Hotel",
    "itinerary": "Roteiro",
    "activity": "Passeio",
    "ticket": "Ticket",
    "reference": "Referência",
}

def build_trip_ics(trip, items) -> str:
    cal = Calendar()

    # Evento principal: viagem inteira (all-day-like, mas com horário)
    main = Event()
    main.name = f"{trip.title} - {trip.destination}"
    main.begin = datetime.combine(trip.start_date, time(9, 0))
    main.end = datetime.combine(trip.end_date, time(20, 0))
    main.description = "Viagem criada no Trip Planner"
    cal.events.add(main)

    # Itens datados viram eventos
    for it in items:
        if not it.item_date:
            continue

        e = Event()
        label = CATEGORY_TITLE.get(it.category, it.category.upper())
        e.name = f"[{label}] {it.title}"
        e.begin = datetime.combine(it.item_date, time(10, 0))
        e.duration = timedelta(hours=1)

        desc_parts = []
        if it.url:
            desc_parts.append(it.url)
        if it.notes:
            desc_parts.append(it.notes)
        e.description = "\n\n".join(desc_parts) if desc_parts else ""

        cal.events.add(e)

    return str(cal)
