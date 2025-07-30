from pathlib import Path

# 1. Bring in the Factory and the KV Builder *first*
from kivy.factory import Factory      # for .register(...)
from kivy.lang    import Builder      # for .load_file(...)

# 2. App + ScreenManager
from kivy.app              import App   # type: ignore
from kivy.uix.screenmanager import ScreenManager   # type: ignore

from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

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
    def build(self):
        self.gps = GPSTracker.get_instance()
        self.gps.start()

        # Weather auto‑refresh & DB hook
        self.weather = Weather(db_hook=self._store_weather)

        return Root()

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
        # 1. stop GPS & weather timers
        self.gps.stop()
        # 2. end open Session row
        sess = getattr(self, "current_session", None)
        if sess:
            db.end_session(sess)
            del self.current_session
        # 3. go back to “home”
        self.root.current = "home"

    # unchanged save_catch / on_stop …

if __name__ == "__main__":
    FishTrackerApp().run()
