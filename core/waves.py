# core/waves.py
from __future__ import annotations

from datetime import datetime, timezone
import requests, logging, time
from typing import Dict, Tuple, Optional, Union, Callable
from kivy.clock import Clock  # type: ignore

# ---------- project- / param-IDs you care about ------------------------
PROJECT_ID = 55                       # your WQDataLIVE project
PARAM_IDS  = {
    56985: "wind_speed_mph",
    56986: "max_wind_speed_mph",
    56987: "wind_direction_deg",
    56998: "air_temp_f",
    57009: "sig_wave_ft",
    57010: "dominant_wave_period_s",
    57011: "dominant_wave_direction_deg",
    57013: "max_wave_ft",
}

# ---------- low-level helper ------------------------------------------
def _latest(project_id: int, param_id: int) -> Tuple[datetime, float]:
    """Return (UTC-timestamp, value) for the newest sample of one parameter."""
    url  = f"https://www.wqdatalive.com/public/{project_id}/data"
    resp = requests.post(url, data={"paramID": param_id}, timeout=10)
    resp.raise_for_status()
    js   = resp.json()
    if js.get("error"):
        raise RuntimeError(js["error"])

    ts_ms, value = js["data"][-1]          # newest sample is last
    return datetime.fromtimestamp(ts_ms / 1_000, tz=timezone.utc), float(value)

# ---------- public convenience layer ----------------------------------
class Weather:
    """Fetches buoy parameters and caches them for *CACHE_SEC* seconds."""
    CACHE_SEC = 600          # 10 min
    POLL_SEC  = 1800         # 30 min

    def __init__(self, project_id: int = PROJECT_ID, db_hook: Callable | None = None):
        ...
        self._last_fetch = 0.0
        self._db_hook    = db_hook      # called with (weather_obj) after each *new* fetch
        self.project_id = project_id

        # kick‑off timer
        Clock.schedule_interval(lambda *_: self.refresh(), self.POLL_SEC)
        self.refresh(force=True)        # first download right away

    def __getattr__(self, name: str) -> Union[float, str, None]:
        if name in PARAM_IDS.values():
            return self.data.get(name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

       # ── allow app to register a post‑refresh callback ───────────────
    def set_refresh_hook(self, fn):
        """fn(weather_obj) is called *only* when new data was downloaded."""
        self._on_refresh = fn

    # ── main entry point ─────────────────────────────────────────────

    def refresh(self, force: bool = False) -> None:
        if not force and time.time() - self._last_fetch < self.CACHE_SEC:
            return

        try:
            latest_time = None
            buf: Dict[str, Union[float, str]] = {}
            for pid, key in PARAM_IDS.items():
                ts, val = _latest(self.project_id, pid)
                buf[key] = val
                if latest_time is None or ts > latest_time:
                    latest_time = ts
        except Exception as exc:
            logging.warning("Weather refresh failed: %s", exc)
            return

        self.time_utc = latest_time
        self.data     = buf
        self._last_fetch = time.time()

        # derived fields
        if self.wind_direction_deg is not None:
            self.data["wind_direction_compass"] = self.deg_to_compass8(self.wind_direction_deg)
        if self.dominant_wave_direction_deg is not None:
            self.data["dominant_wave_direction_compass"] = self.deg_to_compass8(
                self.dominant_wave_direction_deg
            )

        if self._db_hook:
            self._db_hook(self)
            
    def deg_to_compass8(self, deg: float):
        '''Convert a bearing in degrees to one of the eight compass points.'''
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        # Divide by 45°, round to nearest index, wrap around with modulo
        if deg:
            idx = round(deg / 45) % 8
            return directions[idx]
        return



