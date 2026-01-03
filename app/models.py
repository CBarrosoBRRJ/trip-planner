from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from .db import Base


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True, nullable=False)

    title = Column(String(200), nullable=False)
    destination = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    currency = Column(String(8), nullable=False, default="BRL")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    items = relationship("TripItem", back_populates="trip", cascade="all, delete-orphan")
    participants = relationship("TripParticipant", back_populates="trip", cascade="all, delete-orphan")


class TripItem(Base):
    __tablename__ = "trip_items"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), index=True, nullable=False)

    category = Column(String(50), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    item_date = Column(Date, nullable=True)

    url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # custo em centavos
    cost = Column(Integer, nullable=True)

    # JSON como string (pra meta: endereço, hora, companhia, etc.)
    meta_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    trip = relationship("Trip", back_populates="items")


class TripParticipant(Base):
    __tablename__ = "trip_participants"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), index=True, nullable=False)

    name = Column(String(120), nullable=False)
    email = Column(String(200), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    trip = relationship("Trip", back_populates="participants")


Index("ix_trip_participants_trip_id_email", TripParticipant.trip_id, TripParticipant.email)
