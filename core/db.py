"""FishTracker database layer
================================
SQLite + Peewee ORM schema and helpers.

Usage (simplified)::
    from core import db
    db.initialize()  # create tables if first run

    s = db.start_session()
    db.log_gps(s, lat, lon, speed)
    db.log_weather(s, **weather_dict)
    db.end_session(s)

All timestamps are stored in UTC.
"""

from __future__ import annotations

import os
import datetime as _dt
from typing import Optional

# Third‑party
from peewee import (
    SqliteDatabase,
    Model,
    AutoField,
    DateTimeField,
    FloatField,
    CharField,
    TextField,
    ForeignKeyField
)


# ---------------------------------------------------------------------------
# 1. Where to place the DB file
# ---------------------------------------------------------------------------

def _get_db_path() -> str:
    """Return a writeable path for the SQLite file, platform‑aware."""
    try:
        # Android: use internal app storage (no external permission required)
        from android.storage import app_storage_path  # type: ignore

        base_path = app_storage_path()
    except (ImportError, ModuleNotFoundError):
        # Desktop / dev environment: put next to this file inside /core
        base_path = os.path.dirname(__file__)

    os.makedirs(base_path, exist_ok=True)
    return os.path.join(base_path, "fishtracker.db")


_db = SqliteDatabase(_get_db_path(), pragmas={
    "journal_mode": "wal",  # better concurrency
    "foreign_keys": 1,       # enforce FK constraints
})


# ---------------------------------------------------------------------------
# 2. Base model
# ---------------------------------------------------------------------------


class _BaseModel(Model):
    class Meta:
        database = _db


# ---------------------------------------------------------------------------
# 3. Schema (tables)
# ---------------------------------------------------------------------------


class Session(_BaseModel):
    """A single outing (start → end)."""

    id = AutoField()
    start_time = DateTimeField()
    end_time = DateTimeField(null=True)
    notes = TextField(null=True)


class GPSLog(_BaseModel):
    """Raw GPS samples (≈ one every few seconds)."""

    id = AutoField()
    session = ForeignKeyField(Session, backref="gps_logs", on_delete="CASCADE")
    timestamp = DateTimeField()
    latitude = FloatField()
    longitude = FloatField()
    speed_kph = FloatField(null=True)
    est_depth_m = FloatField(null=True)


class Catch(_BaseModel):
    """Each fish caught."""

    id = AutoField()
    session = ForeignKeyField(Session, backref="catches", on_delete="CASCADE")
    timestamp = DateTimeField()
    species = CharField()
    length_cm = FloatField(null=True)
    weight_kg = FloatField(null=True)
    bait = CharField(null=True)
    notes = TextField(null=True)
    latitude = FloatField(null=True)
    longitude = FloatField(null=True)


class WeatherLog(_BaseModel):
    id = AutoField()
    session = ForeignKeyField(Session, backref="weather_logs", on_delete="CASCADE")
    timestamp = DateTimeField()
    temp_c = FloatField(null=True)
    wind_kph = FloatField(null=True)
    pressure_hpa = FloatField(null=True)
    conditions = CharField(null=True)


# ---------------------------------------------------------------------------
# 4. Lifecycle helpers
# ---------------------------------------------------------------------------


def initialize() -> None:
    """Create tables if they don’t exist. Call once at app startup."""
    _db.connect(reuse_if_open=True)
    _db.create_tables([Session, GPSLog, Catch, WeatherLog])
    _db.close()


# ---------------------------------------------------------------------------
# 5. High‑level write helpers
# ---------------------------------------------------------------------------


def _utcnow() -> _dt.datetime:
    return _dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc)


def start_session(notes: str | None = None) -> Session:
    """Insert a new *open* Session row and return the model."""
    return Session.create(start_time=_utcnow(), notes=notes)


def end_session(session: Session | int) -> None:
    """Set *end_time* to now."""
    session_id = session.id if isinstance(session, Session) else session
    (Session
     .update({Session.end_time: _utcnow()})
     .where(Session.id == session_id)
     .execute())


def log_gps(
    session: Session | int,
    latitude: float,
    longitude: float,
    speed_kph: Optional[float] = None,
    est_depth_m: Optional[float] = None,
    timestamp: Optional[_dt.datetime] = None,
) -> GPSLog:
    """Add one GPS sample."""
    return GPSLog.create(
        session=session,
        timestamp=timestamp or _utcnow(),
        latitude=latitude,
        longitude=longitude,
        speed_kph=speed_kph,
        est_depth_m=est_depth_m,
    )


def log_catch(
    session: Session | int,
    species: str,
    latitude: float,
    longitude: float,
    length_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    bait: Optional[str] = None,
    notes: Optional[str] = None,
    timestamp: Optional[_dt.datetime] = None,
) -> Catch:
    return Catch.create(
        session=session,
        timestamp=timestamp or _utcnow(),
        species=species,
        latitude=latitude,
        longitude=longitude,
        length_cm=length_cm,
        weight_kg=weight_kg,
        bait=bait,
        notes=notes,
    )


def log_weather(
    session: Session | int,
    temp_c: Optional[float] = None,
    wind_kph: Optional[float] = None,
    pressure_hpa: Optional[float] = None,
    conditions: Optional[str] = None,
    timestamp: Optional[_dt.datetime] = None,
) -> WeatherLog:
    return WeatherLog.create(
        session=session,
        timestamp=timestamp or _utcnow(),
        temp_c=temp_c,
        wind_kph=wind_kph,
        pressure_hpa=pressure_hpa,
        conditions=conditions,
    )


# ---------------------------------------------------------------------------
# 6. Simple read helpers (examples)
# ---------------------------------------------------------------------------


def get_session_summary(session: Session | int):
    """Return total catches, distance (km), duration (h) for one session."""
    session_id = session.id if isinstance(session, Session) else session

    sess = Session.get_by_id(session_id)

    catches = Catch.select().where(Catch.session == session_id).count()

    # distance: naive Haversine accumulation (development‑time only)
    from math import radians, sin, cos, sqrt, atan2

    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0  # km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    coords = list(
        GPSLog
        .select(GPSLog.latitude, GPSLog.longitude)
        .where(GPSLog.session == session_id)
        .order_by(GPSLog.timestamp)
    )
    dist = 0.0
    for p1, p2 in zip(coords, coords[1:]):
        dist += _haversine(p1.latitude, p1.longitude, p2.latitude, p2.longitude)

    duration_h = None
    if sess.end_time:
        duration_h = (sess.end_time - sess.start_time).total_seconds() / 3600.0

    return {
        "n_catches": catches,
        "distance_km": round(dist, 2),
        "duration_h": round(duration_h, 2) if duration_h else None,
    }


# ---------------------------------------------------------------------------
# 7. Lookup Helpers
# ---------------------------------------------------------------------------
from peewee import fn

def distinct_species() -> list[str]:
    """Return alphabetic list of unique species already logged."""
    rows = (Catch
            .select(Catch.species)
            .distinct()
            .order_by(fn.LOWER(Catch.species)))
    return [r.species for r in rows]

def distinct_baits() -> list[str]:

    rows = (Catch
            .select(Catch.bait)
            .where(Catch.bait.is_null(False))   # exclude NULL
            .distinct()
            .order_by(fn.LOWER(Catch.bait)))
    return [r.bait for r in rows]


# ---------------------------------------------------------------------------
# 8. CLI test (only runs on desktop)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    initialize()
    s = start_session("debug session")
    log_gps(s, 45.0, -122.0, 5.5)
    log_weather(s, temp_c=21.3, wind_kph=3)
    log_catch(s, "trout", 45.0, -122.0, length_cm=81.3)
    end_session(s)
    print(get_session_summary(s))
