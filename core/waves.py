# core/waves.py
from __future__ import annotations

from datetime import datetime, timezone
import requests
from typing import Dict, Tuple, Optional, Literal

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
    """Container that fetches *all* parameters in one call to .refresh()."""

    def __init__(self, project_id: int = PROJECT_ID):
        self.project_id = project_id
        self.data: Dict[str, Optional[float]] = {}
        self.time_utc: Optional[datetime] = None

        self.wind_direction_deg = self.deg_to_compass8(self.wind_direction_deg)
        self.dominant_wave_direction_deg = self.deg_to_compass8(self.dominant_wave_direction_deg)


    def __getattr__(self, name: str) -> Optional[float]:
        if name in PARAM_IDS.values():
            return self.data.get(name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    # -- API ------------------------------------------------------------
    def refresh(self) -> None:
        """Download the newest set of readings and cache them on the object."""
        latest_time = None
        buf: Dict[str, float] = {}

        for pid, key in PARAM_IDS.items():
            ts, val = _latest(self.project_id, pid)
            buf[key] = val
            if latest_time is None or ts > latest_time:
                latest_time = ts

        self.time_utc = latest_time
        self.data     = buf

    def deg_to_compass8(self, deg: float):
        '''Convert a bearing in degrees to one of the eight compass points.'''
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        # Divide by 45°, round to nearest index, wrap around with modulo
        if deg:
            idx = round(deg / 45) % 8
            return directions[idx]
        return



