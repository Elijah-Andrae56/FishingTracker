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
    CACHE_SEC = 600          # 10 min, minimum seconds to reuse cached data
    POLL_SEC  = 1800         # 30 min, background polling cadence (seconds)

    def __init__(self, project_id: int = PROJECT_ID, db_hook: Optional[Callable] = None):
        self._lock = threading.Lock()
        self._fetching = False
        self._last_fetch = 0.0
        self._last_error = None
        self._db_hook = db_hook
        self.project_id = project_id

        # NEW: initialize caches + optional on_refresh hook
        self._on_refresh: Optional[Callable[["Weather"], None]] = None
        self.data: Dict[str, Optional[float]] = {name: None for name in PARAM_IDS.values()}
        self.data_ts: Dict[str, Optional[datetime]] = {name: None for name in PARAM_IDS.values()}

        # Schedule periodic, non-blocking refreshes
        Clock.schedule_interval(lambda *_: self.refresh(), self.POLL_SEC)
        # Defer first refresh until after the first frame so UI draws immediately
        Clock.schedule_once(lambda *_: self.refresh(force=True), 0)

    def __getattr__(self, name: str) -> Union[float, str, None]:
        if name in PARAM_IDS.values():
            return self.data.get(name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def set_refresh_hook(self, fn: Callable[["Weather"], None]) -> None:
        """fn(weather_obj) is called *only* when new data was downloaded."""
        self._on_refresh = fn

    def refresh(self, force: bool = False, callback: Optional[Callable[["Weather"], None]] = None) -> None:
        """
        Non-blocking weather refresh. If a fetch is needed, this spawns a worker
        thread to do network I/O, then posts results back to the main thread.
        If `callback` is provided, it is called on the main thread after the
        refresh attempt (whether success or failure).
        """
        now = time.time()

        # If cache is fresh and not forced, nothing to do.
        if not force and (now - self._last_fetch) < self.CACHE_SEC:
            if callback:
                Clock.schedule_once(lambda *_: callback(self), 0)
            return

        # Prevent concurrent workers.
        with self._lock:
            if self._fetching:
                return
            self._fetching = True

        def worker():
            ok = False
            err = None
            changed = False
            try:
                logging.info("Weather: fetching…")

                # Build a new snapshot by pulling the newest sample for each param.
                new_data: Dict[str, Optional[float]] = {}
                new_ts: Dict[str, Optional[datetime]] = {}

                for pid, name in PARAM_IDS.items():
                    try:
                        ts, val = _latest(self.project_id, pid)
                        new_data[name] = val
                        new_ts[name] = ts
                    except Exception as perr:
                        # Keep old value for this param if fetch fails
                        logging.warning("Weather: param %s (%s) fetch failed: %s", name, pid, perr)
                        new_data[name] = self.data.get(name)
                        new_ts[name] = self.data_ts.get(name)

                # Detect any change (value or timestamp)
                for key in new_data.keys():
                    old_v = self.data.get(key)
                    old_t = self.data_ts.get(key)
                    if (old_v is None) != (new_data[key] is None):
                        changed = True; break
                    if isinstance(old_v, float) and isinstance(new_data[key], float):
                        if abs(old_v - new_data[key]) > 1e-6:
                            changed = True; break
                    if old_t != new_ts[key]:
                        changed = True; break

                ok = True

            except Exception as e:
                err = e
                self._last_error = str(e)
                logging.exception("Weather.refresh failed")
            finally:
                def finish(_dt):
                    # Run on the main thread.
                    if ok:
                        # Apply the snapshot
                        try:
                            self.data = new_data
                            self.data_ts = new_ts
                        except UnboundLocalError:
                            pass
                        self._last_fetch = time.time()
                        logging.info("Weather: fetch done")

                        # Optional DB side-effects
                        if self._db_hook:
                            try:
                                self._db_hook(self)
                            except Exception:
                                logging.exception("Weather db_hook failed")

                        # Notify only when new data actually arrived
                        if changed and self._on_refresh:
                            try:
                                self._on_refresh(self)
                            except Exception:
                                logging.exception("Weather on_refresh hook failed")
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
