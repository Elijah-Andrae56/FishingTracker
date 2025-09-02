# core/waves.py
from __future__ import annotations

from datetime import datetime, timezone
import requests, logging, time, threading
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
    resp = requests.post(url, data={"paramID": param_id}, timeout=(3, 10))
    resp.raise_for_status()
    js   = resp.json()
    if js.get("error"):
        raise RuntimeError(js["error"])

    ts_ms, value = js["data"][-1]          # newest sample is last
    return datetime.fromtimestamp(ts_ms / 1_000, tz=timezone.utc), float(value)

# ---------- public convenience layer ----------------------------------
class Weather:
    """Fetches buoy parameters and caches them for *CACHE_SEC* seconds."""
    CACHE_SEC = 600          # 10 min
    POLL_SEC  = 1800         # 30 min

    def __init__(self, project_id: int = PROJECT_ID, db_hook: Callable | None = None):
        import threading
        self._lock = threading.Lock()
        self._fetching = False
        self._last_fetch = 0.0
        self._last_error = None
        self._db_hook    = db_hook
        self.project_id  = project_id

        # initialize caches so UI can read placeholders safely
        self.time_utc: Optional[datetime] = None
        self.data: Dict[str, Optional[float]] = {name: None for name in PARAM_IDS.values()}
        self._on_refresh: Optional[Callable[["Weather"], None]] = None  # optional UI hook

        # schedule non-blocking polling; defer first fetch so UI can render
        Clock.schedule_interval(lambda *_: self.refresh(), self.POLL_SEC)
        Clock.schedule_once(lambda *_: self.refresh(force=True), 0)

    def __getattr__(self, name: str) -> Union[float, str, None]:
        if name in PARAM_IDS.values():
            return self.data.get(name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def set_refresh_hook(self, fn):
        """fn(weather_obj) is called *only* when new data was downloaded."""
        self._on_refresh = fn

    def refresh(self, force: bool = False, callback=None) -> None:
        """
        Non-blocking weather refresh. If a fetch is needed, runs a worker thread
        that does network I/O, then applies results on the main thread.
        """
        import threading, time, logging

        # respect cache unless forced
        if not force and (time.time() - self._last_fetch) < self.CACHE_SEC:
            if callback:
                Clock.schedule_once(lambda *_: callback(self), 0)
            return

        # prevent concurrent workers
        with self._lock:
            if self._fetching:
                return
            self._fetching = True

        def worker():
            ok = False
            err = None
            try:
                logging.info("Weather: fetching…")
                latest_time: Optional[datetime] = None
                buf: Dict[str, Union[float, str, None]] = {}

                for pid, key in PARAM_IDS.items():
                    try:
                        ts, val = _latest(self.project_id, pid)
                        buf[key] = val
                        if latest_time is None or ts > latest_time:
                            latest_time = ts
                    except Exception as e:
                        # keep prior value for this param on individual failures
                        logging.warning("Weather param %s failed: %s", key, e)
                        buf[key] = self.data.get(key)

                ok = True
            except Exception as e:
                err = e
                self._last_error = str(e)
                logging.exception("Weather.refresh failed")
            finally:
                def finish(_dt):
                    # apply on UI thread
                    if ok:
                        self.time_utc = latest_time
                        changed = (buf != self.data)
                        self.data = buf  # replace snapshot
                        self._last_fetch = time.time()

                        # # derived fields
                        # if self.wind_direction_deg is not None:
                        #     self.data["wind_direction_compass"] = self.deg_to_compass8(self.wind_direction_deg)
                        # if self.dominant_wave_direction_deg is not None:
                        #     self.data["dominant_wave_direction_compass"] = self.deg_to_compass8(
                        #         self.dominant_wave_direction_deg
                        #     )

                        if self._db_hook:
                            try:
                                self._db_hook(self)
                            except Exception:
                                logging.exception("Weather db_hook failed")

                        if changed and self._on_refresh:
                            try:
                                self._on_refresh(self)
                            except Exception:
                                logging.exception("Weather on_refresh failed")
                    else:
                        logging.info("Weather: fetch failed: %s", err)

                    with self._lock:
                        self._fetching = False

                    if callback:
                        try:
                            callback(self)
                        except Exception:
                            logging.exception("Weather callback failed")

                Clock.schedule_once(finish, 0)

        threading.Thread(target=worker, daemon=True).start()
