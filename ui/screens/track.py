# ui/screens/track.py
from pathlib import Path

from kivy.app import App                          # type: ignore
from kivy.clock import Clock                      # type: ignore
from kivy.uix.screenmanager import Screen         # type: ignore
from kivy.resources import resource_add_path, resource_find # type: ignore
from kivy_garden.mapview import MapMarker         # type: ignore

from core import db

# 1) register your icon folder so resource_find() works at runtime:
resource_add_path(str(Path(__file__).parent.parent / "img"))


class TrackScreen(Screen):
    # Your test / boating area center:
    DEFAULT_START = (42.177377, -80.034476)  # e.g. Lake Erie

    def on_enter(self):
        app = App.get_running_app()

        # 2) If no session yet, start one now
        if not hasattr(app, "current_session"):
            app.current_session = db.start_session()

        # 3) MapView & markers
        mv = self.ids.mapview
        lat0, lon0 = self.DEFAULT_START

        # 3a) center map on your start
        mv.center_on(lat0, lon0)

        # 3b) one-time “start” pin
        img_start = resource_find("start.png")
        if img_start:
            # keep a reference so we can move it later
            self._start_marker = MapMarker(lat=lat0, lon=lon0, source=img_start)
            mv.add_widget(self._start_marker)

        # 3c) create your “boat” marker at start too
        img_boat = resource_find("boat.png")
        self._pos_marker = MapMarker(lat=lat0 + 0.05, lon=lon0 + 0.05, source=img_boat)
        mv.add_widget(self._pos_marker)

        # 4) subscribe GPS fixes & buoy timer
        self._first_fix = None
        self._gps_cb    = app.gps.subscribe(self._on_fix)
        self._wx_event  = Clock.schedule_interval(self.update_wave, 1800)
        # update labels immediately
        self.update_wave()

    def on_leave(self):
        app = App.get_running_app()
        app.gps.unsubscribe(self._gps_cb)
        self._wx_event.cancel()

    def _on_fix(self, lat, lon, spd):
        """Called on every GPS fix."""
        # 1) live speed label
        self.ids.speed_lbl.text = f"{spd:4.1f} kn"

        # 2) persist fix
        db.log_gps(App.get_running_app().current_session, lat, lon, speed_kph=spd)

        # 3) move your “boat” marker
        self._pos_marker.lat = lat
        self._pos_marker.lon = lon

        # 4) center map
        self.ids.mapview.center_on(lat, lon)

        # ——— on the very first real fix, snap the start pin to that position ———
        if self._first_fix is None:
            self._first_fix = (lat, lon)
            # reposition the start marker from DEFAULT_START to the user's actual start
            self._start_marker.lat = lat
            self._start_marker.lon = lon

    def update_wave(self, *_):
        """Refresh buoy + update labels."""
        w = App.get_running_app().weather
        w.refresh()
        self.ids.wave_lbl.text = (
            f"Wind {w.wind_speed_mph or '–'} mph   "
            f"Sig  {w.sig_wave_ft    or '–'} ft"
        )
