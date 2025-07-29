from kivy.app import App  # type: ignore
from kivy.clock import Clock  # type: ignore
from kivy.uix.screenmanager import ScreenManager, Screen  # type: ignore
from kivy.uix.popup import Popup  # type: ignore
from kivy.properties import StringProperty, ListProperty  # type: ignore
from kivy.factory import Factory # type: ignore

from ui.screens.popup_weather import WeatherPopup
from ui.screens.home import HomeScreen
from ui.screens.track import TrackScreen

from core.gps_utils import GPSTracker, last_fix
from core.waves import Weather
from core import db
db.initialize()

from pathlib import Path

# ------------------------------------------------------------------- UI
class Root(ScreenManager):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.add_widget(HomeScreen())   # new welcome page
        self.add_widget(TrackScreen())  # already exists or stub
        self.add_widget(LogbookScreen())


class LogbookScreen(Screen):
    pass

class LogCatchPopup(Popup):
    init_bait_text     = StringProperty("Select Bait")
    bait_choices       = ListProperty()
    init_species_text  = StringProperty("Select Species")
    species_choices    = ListProperty()

    def on_open(self):
        """Load distinct choices from DB each time the popup is shown."""
        self.species_choices = db.distinct_species() or ["Bass", "Perch", "Walleye"]
        self.bait_choices    = db.distinct_baits() or ["Crankbait", "Worm", "Minnow"]

Factory.register("LogCatchPopup", cls=LogCatchPopup)
Factory.register("WeatherPopup", cls=WeatherPopup)

# Load KV files ***after*** all classes are defined
KV_DIR = Path(__file__).parent / "ui" / "kv"
from kivy.lang import Builder  # type: ignore
for kv in ("main.kv", "catch.kv", "home.kv", "weather.kv", "track.kv", "logbook.kv"):
    Builder.load_file(str(KV_DIR / kv))


# ------------------------------------------------------------------- App
class FishTrackerApp(App):
    def build(self):
        self.gps = GPSTracker.get_instance()
        self.gps.start()
        self.weather = Weather()
        return Root()
    
    def save_catch(self, species: str, bait: str, length_txt: str, notes: str) -> None:
        coords = last_fix()
        if coords:
            lat, lon, _ = coords
        else:
            lat = lon = 0.0

        length_in = float(length_txt) if length_txt else None
        length_cm = length_in * 2.54 if length_in else None

        species = species.strip() or self.root_window.children[0].ids.species_txt.text.strip()
        bait    = bait.strip()    or self.root_window.children[0].ids.bait_txt.text.strip()

        db.log_catch(1, species, lat, lon, length_cm=length_cm, bait=bait, notes=notes)

    def on_stop(self):
        self.gps.stop()

if __name__ == "__main__":
    FishTrackerApp().run()
