"""
core/gps_utils.py
=================

Unified access to the device’s GPS.  Works on Android (Plyer) *and* on
desktop where it produces deterministic fake data so the UI never breaks.

Public API
----------

>>> tracker = GPSTracker.get_instance()
>>> tracker.start()          # one-time at app launch
>>> lat, lon, spd = last_fix() or (None, None, None)
>>> tracker.stop()           # on App.on_stop()
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple
import sys
import time
import math

# ---------------------------------------------------------------------------#
# 0. Platform detection & Plyer import
# ---------------------------------------------------------------------------#
try:                    # Android / mobile
    from plyer import gps # type: ignore
    _PLYER_AVAILABLE = True
except Exception:       # Desktop
    gps = None          # type: ignore
    _PLYER_AVAILABLE = False

_IS_ANDROID = _PLYER_AVAILABLE and (sys.platform == "android")

# ---------------------------------------------------------------------------#
# 1. Singleton Tracker
# ---------------------------------------------------------------------------#
class GPSTracker:
    """
    Singleton wrapper around Plyer’s GPS façade.  On desktop it generates a
    slow spiral pattern so charts have something to draw.
    """

    _instance: "GPSTracker | None" = None

    # ------------------------- creation ---------------------------------- #
    def __init__(self) -> None:
        self._lat: float = 0.0
        self._lon: float = 0.0
        self._speed_mps: float = 0.0
        self._enabled: bool = False
        self._subscribers: list[Callable[[float, float, float], None]] = []

        # desktop fake-GPS state
        self._t0 = time.time()

    @classmethod
    def get_instance(cls) -> "GPSTracker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------- public props ------------------------------ #
    @property
    def speed_kph(self) -> float:
        return self._speed_mps * 3.6

    @property
    def speed_knots(self) -> float:
        return self._speed_mps * 1.94384

    @property
    def latlon(self) -> Tuple[float, float]:
        return self._lat, self._lon

    # ------------------------- lifecycle --------------------------------- #
    def start(self) -> None:
        """Begin receiving location updates."""
        if self._enabled:
            return

        if _PLYER_AVAILABLE:
            try:
                gps.configure(on_location=self._on_location,
                              on_status=self._on_status)
                # minTime 1000 ms, minDistance 1 m keeps power low.
                gps.start(minTime=1000, minDistance=1)
                self._enabled = True
            except NotImplementedError:
                print("⚠  Plyer GPS not implemented; falling back to stub.")
        else:
            # Desktop stub: start a timer loop in Kivy’s Clock
            from kivy.clock import Clock
            Clock.schedule_interval(self._fake_desktop_gps, 1.0)
            self._enabled = True
            print("ℹ  Desktop GPS stub enabled – spiral trajectory.")

    def stop(self) -> None:
        if not self._enabled:
            return
        if _PLYER_AVAILABLE:
            gps.stop()
        self._enabled = False

    # ----------------------- subscriber pattern -------------------------- #
    def subscribe(self, cb: Callable[[float, float, float], None]) -> None:
        """Call *cb(lat, lon, speed_kph)* whenever a new fix arrives."""
        self._subscribers.append(cb)

    # ------------------------- callbacks --------------------------------- #
    def _on_location(self, **kw) -> None:
        self._lat = float(kw.get("lat", 0.0))
        self._lon = float(kw.get("lon", 0.0))
        self._speed_mps = float(kw.get("speed", 0.0))
        for fn in self._subscribers:
            fn(self._lat, self._lon, self.speed_kph)

    def _on_status(self, stype, status) -> None:  # noqa: N802
        # For now, just print notable events
        if status not in ("provider-enabled", "provider-disabled"):
            return
        print(f"ℹ GPS status: {stype} → {status}")

    # ------------------------- desktop stub ------------------------------ #
    def _fake_desktop_gps(self, *_args) -> None:
        """
        Generates a ~25 m radius outward spiral to visualise motion on maps.
        """
        t = time.time() - self._t0
        radius = 0.0002 * t      # lat/lon degrees ≈ 22 m @ 45°N
        angle = 0.5 * t
        self._lat = 45.0000 + radius * math.cos(angle)
        self._lon = -122.0000 + radius * math.sin(angle)
        self._speed_mps = 1.5    # pretend 1.5 m/s (≈ 3 kn)
        for fn in self._subscribers:
            fn(self._lat, self._lon, self.speed_kph)

# ---------------------------------------------------------------------------#
# 2. Convenience helper for other modules
# ---------------------------------------------------------------------------#
def last_fix() -> Optional[Tuple[float, float, float]]:
    """
    Returns *(lat, lon, speed_kph)* or **None** if no location seen yet.
    Call this from anywhere without importing GPSTracker explicitly.
    """
    tr = GPSTracker.get_instance()
    if tr._lat == tr._lon == 0.0 and tr._speed_mps == 0.0:
        return None
    return tr._lat, tr._lon, tr.speed_kph
