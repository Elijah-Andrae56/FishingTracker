from kivy_garden.mapview import MapMarker, MapMarkerPopup # type: ignore
from kivy.resources import resource_add_path, resource_find
from core import db, gps_utils # type: ignore
from kivy.app import App # type: ignore
from kivy.clock import Clock # type: ignore
from kivy.uix.screenmanager import Screen # type: ignore

class TrackScreen(Screen):

    def on_enter(self):
        app = App.get_running_app()
        self._first_fix = None
        self._pos_marker = None        # ← track single current marker
        self._gps_cb = app.gps.subscribe(self._on_fix)

        # 1. subscribe for live GPS updates
        self._gps_cb = app.gps.subscribe(self._on_fix)

        # 2. start 30‑min buoy refresh timer (already exists)
        self._wx_event = Clock.schedule_interval(self.update_wave, 1800)
        self.update_wave()

    def on_leave(self):
        app = App.get_running_app()
        app.gps.unsubscribe(self._gps_cb)
        self._wx_event.cancel()

    # ------------ GPS callback ---------------------------------
    def _on_fix(self, lat, lon, spd):
            self.ids.speed_lbl.text = f"{spd:4.1f} kn"

            # 1 – persist GPS row
            sess = App.get_running_app().current_session
            db.log_gps(sess, lat, lon, speed_kph=spd)

            mv = self.ids.mapview
            mv.center_on(lat, lon)

            # 2 – move or create ONE “current position” marker
            if self._pos_marker is None:
                img = resource_find("boat.png")   # now always resolves
                self._pos_marker = MapMarker(lat=lat, lon=lon, source=img)
                mv.add_widget(self._pos_marker)
            else:
                self._pos_marker.lat = lat
                self._pos_marker.lon = lon

            # 3 – one‑time start pin
            if self._first_fix is None:
                self._first_fix = (lat, lon)
                img = resource_find("start.png")
                mv.add_widget(MapMarker(lat=lat, lon=lon, source=img))

        # TODO Step 5: add point to polyline layer for route

    # ------------ Weather label update -------------------------
    def update_wave(self, *_):
        w = App.get_running_app().weather
        w.refresh()
        self.ids.wave_lbl.text = (
            f"Wind {w.wind_speed_mph or '–'} mph   "
            f"Sig {w.sig_wave_ft or '–'} ft"
        )
