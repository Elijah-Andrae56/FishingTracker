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
        app = App.get_running_app()

        # 1) live speed label — convert from source (knots) to user preference
        self.ids.speed_lbl.text = app.units.fmt("speed", spd, source="kn", precision=1)

        # 2) persist fix — store canonical (kph) in DB
        spd_kph = app.units.to_base("speed", spd, source="kn")
        db.log_gps(app.current_session, lat, lon, speed_kph=spd_kph)

        # 3) move your “boat” marker
        self._pos_marker.lat = lat
        self._pos_marker.lon = lon
        self._route.add_point(lat, lon)

        # … your existing dummy catch logic here …

        # 4) center map
        self.ids.mapview.center_on(lat, lon)

        # First real fix: snap start marker
        if self._first_fix is None:
            self._first_fix = (lat, lon)
            self._start_marker.lat = lat
            self._start_marker.lon = lon

    def _paint_wave_labels(self):
        app = App.get_running_app()
        w = app.weather
        wind_txt = app.units.fmt("speed", w.wind_speed_mph, source="mph", precision=0)
        wave_txt = app.units.fmt("wave",  w.sig_wave_ft,    source="ft",  precision=1)
        self.ids.wave_lbl.text = f"Wind {wind_txt}   Sig {wave_txt}"

    def update_wave(self, *_):
        # 1) Paint immediately from whatever’s cached (non-blocking)
        self._paint_wave_labels()


    def _place_catch_marker(self, catch):
        """
        Add a MapMarkerPopup for this Catch record, so it shows up
        (and opens its own little popup when tapped).
        """
        app = App.get_running_app()
        icon = resource_find("fish.png") or ""
        marker = MapMarkerPopup(lat=catch.latitude, lon=catch.longitude, source=icon)

        length_txt = app.units.fmt_from_base("length", catch.length_cm, precision=1)
        marker.add_widget(Label(text=f"{catch.species}\n{length_txt}"))
        self.ids.mapview.add_widget(marker)
