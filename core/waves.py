# core/waves.py
from __future__ import annotations

from datetime import datetime, timezone
import requests, logging
from typing import Dict, Tuple, Optional, Union

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
        self.data: Dict[str, float | str | None] = {}
        self.time_utc: Optional[datetime] = None

    def __getattr__(self, name: str) -> Union[float, str, None]:
        if name in PARAM_IDS.values():
            return self.data.get(name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    # -- API ------------------------------------------------------------
    def refresh(self) -> None:
        """Download the newest set of readings and cache them on the object."""
        latest_time = None
        buf: Dict[str, Union[float, str, None]] = {}

        for pid, attr_name in PARAM_IDS.items():
            try:
                ts, val = _latest(self.project_id, pid)
            except (requests.RequestException, RuntimeError) as exc:
                logging.warning(
                    "Wave API %s failed for param %s (%s): %s",
                    self.project_id, pid, attr_name, exc
                )
                buf[attr_name] = None
                continue

            buf[attr_name] = val
            if latest_time is None or ts > latest_time:
                latest_time = ts


        self.time_utc = latest_time
        self.data     = buf

        if self.wind_direction_deg is not None:
            self.data["wind_direction_compass"] = self.deg_to_compass8(self.wind_direction_deg) # type: ignore

        if self.dominant_wave_direction_deg is not None:
            self.data["dominant_wave_direction_compass"] = self.deg_to_compass8(self.dominant_wave_direction_deg) # type: ignore



    def deg_to_compass8(self, deg: float):
        '''Convert a bearing in degrees to one of the eight compass points.'''
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        # Divide by 45°, round to nearest index, wrap around with modulo
        if deg:
            idx = round(deg / 45) % 8
            return directions[idx]
        return



