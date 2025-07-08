# core/gps_utils.py
from __future__ import annotations

try:                                    # ➊ import normally on Android
    from plyer import gps
except Exception:                       # ➋ any ImportError on desktop
    gps = None                          #    → we will stub a fake GPS

class GPSTracker:
    """Light wrapper around Plyer’s GPS facade.

    On a desktop this becomes a *no-op* so the rest of the UI can run.
    """

    def __init__(self):
        self._speed = 0.0      # m s-¹
        self._lat   = 0.0
        self._lon   = 0.0
        self._enabled = False

    # ––––– public helpers ––––––––––––––––––––––––––
    @property
    def speed_knots(self) -> float:
        return self._speed * 1.94384      # m/s → kn

    @property
    def latlon(self) -> tuple[float, float]:
        return self._lat, self._lon

    # ––––– lifecycle –––––––––––––––––––––––––––––––
    def start(self):
        if gps is None:                   # ➌ desktop ⇒ do nothing
            print("⚠  GPS not available on this platform – using 0 knots")
            return

        try:
            gps.configure(
                on_location=self._on_location,
                on_status=self._on_status,
            )
            gps.start(minTime=1000, minDistance=1)
            self._enabled = True
        except NotImplementedError:
            print("⚠  Plyer GPS not implemented on this OS – using 0 knots")

    def stop(self):
        if self._enabled and gps:
            gps.stop()

    # ––––– callbacks –––––––––––––––––––––––––––––––
    def _on_location(self, **kw):
        self._lat   = float(kw.get("lat",   0.0))
        self._lon   = float(kw.get("lon",   0.0))
        self._speed = float(kw.get("speed", 0.0))   # m s-¹

    def _on_status(self, stype, status):
        # ignore noisy status updates for now
        pass
