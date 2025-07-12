from kivy.app import App # type: ignore
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen

from core.gps_utils import GPSTracker
from core.waves import Weather

from pathlib import Path, PurePath
kv_path = PurePath("ui/kv/main.kv")
print("→ Loading KV:", kv_path, "exists?", Path(kv_path).is_file())


Builder.load_file("ui/kv/main.kv")      # holds <Root>, <TrackScreen>, ...

# ------------------------------------------------------------------- UI
class Root(ScreenManager):
    pass


class TrackScreen(Screen):
    def on_pre_enter(self):
        app = App.get_running_app()
        # subscribe once; lambda updates the label every fix
        app.gps.subscribe(lambda lat, lon, spd:
                           setattr(self.ids.speed_lbl, "text",
                                   f"Speed: {spd:5.2f} kn"))


class WaveScreen(Screen):
    def on_pre_enter(self):
        self.update_wave()
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

    def on_stop(self):
        self.gps.stop()


if __name__ == "__main__":
    FishTrackerApp().run()
