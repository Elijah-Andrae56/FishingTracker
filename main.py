from pathlib import Path

# 1. Bring in the Factory and the KV Builder *first*
from kivy.factory import Factory                    # type: ignore for .register(...)
from kivy.lang    import Builder                    # type: ignore for .load_file(...)

# 2. App + ScreenManager
from kivy.app              import App               # type: ignore
from kivy.uix.screenmanager import ScreenManager    # type: ignore

from kivy.config import Config                      # type: ignore
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

from kivy.uix.settings import SettingsWithSidebar
from core.units import Units, UNITS_SETTINGS_JSON

# 3. Core services
from core import db
from core.gps_utils import GPSTracker, last_fix
from core.waves     import Weather

# 4. UI screens (these modules define and register their popups)
from ui.screens.home    import HomeScreen
from ui.screens.track   import TrackScreen
from ui.screens.logbook import LogbookScreen

# 5. Popups — import the class so Factory knows about it,
#    then register it under the name you use in your .kv:
from ui.screens.popup_weather import WeatherPopup
Factory.register("WeatherPopup", cls=WeatherPopup)
db.initialize()

# 1. load all KV files up‑front
KV_DIR = Path(__file__).parent / "ui" / "kv"
for kv in ("main.kv", "catch.kv", "home.kv", "weather.kv",
           "track.kv", "logbook.kv"):
    Builder.load_file(str(KV_DIR / kv))

# 2. minimalist Root
class Root(ScreenManager):
    pass    # screens declared in main.kv

# 3. the App
class FishTrackerApp(App):
    settings_cls = SettingsWithSidebar

    def build_config(self, config):
        # Config is persisted in App's user config file automatically
        config.setdefaults("units", {
            "length": "in",
            "weight": "lb",
            "speed": "kn",
            "temp": "F",
            "wave": "ft",
            "distance": "mi",
        })

    def build_settings(self, settings):
        settings.add_json_panel("Units", self.config, data=UNITS_SETTINGS_JSON)

    def on_config_change(self, config, section, key, value):
        # Notify any listeners to repaint when a units setting changes
        if section == "units":
            if hasattr(self, "units"):
                self.units.notify()

    def build(self):
        # 0) Units helper (reads persisted settings via self.config)
        self.units = Units(self.config)

        # 1) Start services that don't depend on root widgets
        self.gps = GPSTracker.get_instance()
        self.gps.start()

        # Weather fetcher (non-blocking), with DB hook
        self.weather = Weather(db_hook=self._store_weather)

        # 2) Build the UI tree and return it
        root = Root()

        # 3) Optional: repaint key screens immediately when units change
        def _on_units_change(_u):
            # Example: the Track screen's wave label should repaint now
            try:
                track = root.get_screen("track")
                # This will paint from cache immediately; your Weather.refresh() remains non-blocking
                track.update_wave()
            except Exception:
                pass
        self.units.bind(_on_units_change)

        return root

    # called by Weather after every *new* fetch
    def _store_weather(self, w):
        session = getattr(self, "current_session", None)
        if session is None:
            session = db.start_session("auto‑wx")
            self.current_session = session

        db.log_weather(
            session,
            temp_c   = (w.air_temp_f - 32) * 5/9 if w.air_temp_f else None,
            wind_kph = w.wind_speed_mph * 1.60934 if w.wind_speed_mph else None,
            conditions = f"W{w.wind_speed_mph or 0}mph"
                         f"/Sig{w.sig_wave_ft or 0}ft",
        )

    def end_trip(self):
            """Stop GPS, close DB session and return to home screen."""
            # 1) stop GPS & weather timers
            try:
                self.gps.stop()
            except NotImplementedError:
                # plyer.gps.stop() isn't implemented on this platform → ignore
                pass

            # 2) end open Session row
            sess = getattr(self, "current_session", None)
            if sess:
                db.end_session(sess)
                del self.current_session

            # 3) go back to “home”
            self.root.current = "home"

    def _to_float_or_none(self, text: str):
        try:
            if not text:
                return None
            t = text.strip()
            if not t:
                return None
            return float(t)
        except (ValueError, TypeError):
            return None

    def save_catch(self, species: str, bait: str, length_txt: str, notes: str):
        # 1) latest coords (or 0,0)
        coords = last_fix() # FIXME Make units change with settings
        if coords:
            lat, lon, _ = coords
        else:
            lat = lon = 0.0

        # 2) parse length in the *display* unit and convert to cm for DB
        length_display = self._to_float_or_none(length_txt)
        length_cm = None if length_display is None else self.units.to_base("length", length_display)

        # 3) ensure there’s a session
        session = getattr(self, "current_session", None)
        if session is None:
            session = db.start_session()
            self.current_session = session

        new_catch = db.log_catch(
            session,
            (species or "UNKNOWN").strip(),
            lat, lon,
            length_cm=length_cm,
            bait=(bait or None),
            notes=(notes or None),
        )

        # 4) add a marker on the map
        track = self.root.get_screen("track")
        track._place_catch_marker(new_catch)

if __name__ == "__main__":
    FishTrackerApp().run()
