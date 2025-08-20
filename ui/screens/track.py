# ui/screens/track.py
from pathlib import Path

from kivy.app import App                          # type: ignore
from kivy.clock import Clock                      # type: ignore
from kivy.uix.screenmanager import Screen         # type: ignore
from kivy.resources import resource_add_path, resource_find # type: ignore
from kivy_garden.mapview import MapMarker, MapMarkerPopup   # type: ignore
from kivy.uix.boxlayout import BoxLayout                    # type: ignore
from kivy.uix.label import Label                            # type: ignore
from core.mapline import MapLine
from core import db
import random

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
        self._pos_marker = MapMarker(lat=lat0, lon=lon0, source=img_boat)
        mv.add_widget(self._pos_marker)

        # 4) subscribe GPS fixes & buoy timer
        self._first_fix = None
        self._gps_cb    = app.gps.subscribe(self._on_fix)
        self._wx_event  = Clock.schedule_interval(self.update_wave, 1800)
        # update labels immediately
        self.update_wave()

        # Initialize the tracking line
        self._route = MapLine(mapview=mv)
        mv.add_widget(self._route)

        # Load existing catch markers
        self._load_existing_catch_markers()

    def _load_existing_catch_markers(self):
        """Place one marker per Catch in the current session."""
        session = App.get_running_app().current_session
        for c in db.Catch.select().where(db.Catch.session == session):
            # only place if we haven’t already
            self._place_catch_marker(c)

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

        self._route.add_point(lat, lon)
             
        # on desktop, 5% of fixes become a dummy test catch
        if random.random() < 0.05:
            class Fake: pass
            f = Fake()
            f.latitude   = lat              # type: ignore
            f.longitude  = lon              # type: ignore
            f.species    = "TEST"           # type: ignore
            f.length_cm  = 25.0             # type: ignore
            f.weight_kg  = 0.75             # type: ignore
            self._place_catch_marker(f)   


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

    def place_catch_marker(self, catch):
        """
        Add a MapMarkerPopup for this Catch record, so it shows up
        (and opens its own little popup when tapped).
        """
        icon = resource_find("fish.png") or ""
        marker = MapMarkerPopup(
            lat=catch.latitude,
            lon=catch.longitude,
            source=icon
        )
        # (optionally) attach some content to marker.popup content,
        # e.g. a Label with species/length/bait…
        marker.add_widget(
            Label(text=f"{catch.species}\n{catch.length_cm:.1f} cm")
        )
        self.ids.mapview.add_widget(marker)

