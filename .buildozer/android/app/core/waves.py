# core/waves.py
from __future__ import annotations

from datetime import datetime, timezone
import requests
from typing import Dict, Tuple, Optional

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

    # -- niceties – feel free to add more properties --------------------
    @property
    def sig_wave_ft(self) -> Optional[float]:
        return self.data.get("sig_wave_ft")

    @property
    def max_wave_ft(self) -> Optional[float]:
        return self.data.get("max_wave_ft")

    @property
    def wind_gust_mph(self) -> Optional[float]:
        return self.data.get("max_wind_speed_mph")
