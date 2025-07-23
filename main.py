from kivy.app import App # type: ignore
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen

from core.gps_utils import GPSTracker, last_fix
from core.waves import Weather
from core import db

from pathlib import Path

KV_DIR = Path(__file__).parent / "ui" / "kv"
Builder.load_file(str(KV_DIR / "main.kv"))      # holds <Root>, <TrackScreen>, ...
Builder.load_file(str(KV_DIR / "catch.kv"))

# ------------------------------------------------------------------- UI
class Root(ScreenManager):
    pass
 
    def on_pre_enter(self):
        app = App.get_running_app()
        # subscribe once; lambda updates the label every fix
        app.gps.subscribe(lambda lat, lon, spd:
                           setattr(self.ids.speed_lbl, "text",
                                   f"Speed: {spd:5.2f} kn"))
        Clock.schedule_interval(self.update_wave, 1800)

    def update_wave(self, *_):
        w = App.get_running_app().weather
        w.refresh()
        self.ids.wave_lbl.text = (
            f"Wind {w.wind_speed_mph or '-'} mph\n"
            f"Sig Wave {w.sig_wave_ft or '-'} ft"
        )

class LogbookScreen(Screen):
    pass


# ------------------------------------------------------------------- App
class FishTrackerApp(App):
    def build(self):
        # services
        self.gps = GPSTracker.get_instance()
        self.gps.start()

        self.weather = Weather()

        return Root()           # <Root> rule builds all screens
    
    def save_catch(self, species: str, bait: str, length_txt: str, notes: str) -> None:
        """Persist one catch to the database."""
        coords = last_fix()
        if coords:
            lat, lon, _ = coords
        else:
            lat = lon = 0.0

        length_in = float(length_txt) if length_txt else None
        db.log_catch(1, species, lat, lon, length_in=length_in, bait=bait, notes=notes)
        

    def on_stop(self):
        self.gps.stop()


if __name__ == "__main__":
    FishTrackerApp().run()
