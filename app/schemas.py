from datetime import date
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


Category = Literal[
    "itinerary",
    "activity",
    "restaurant",
    "hotel",
    "flight",
    "ticket",
    "reference",
    "notes",
]


class TripCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    destination: str = Field(min_length=2, max_length=200)
    start_date: date
    end_date: date
    currency: str = "BRL"


class ItemCreate(BaseModel):
    category: Category
    title: str = Field(min_length=1, max_length=200)
    item_date: Optional[date] = None
    url: Optional[str] = None
    notes: Optional[str] = None
    cost: Optional[float] = None  # em reais, vamos converter pra centavos no service
    meta: Optional[Dict[str, Any]] = None


class ParticipantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: Optional[str] = Field(default=None, max_length=200)
