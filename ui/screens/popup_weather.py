from kivy.uix.popup import Popup # type: ignore
from kivy.properties import NumericProperty # type: ignore
from kivy.clock import Clock # type: ignore
from kivy.app import App # type: ignore

class WeatherPopup(Popup):
    wind  = NumericProperty(0)
    wave  = NumericProperty(0)
    temp  = NumericProperty(0)

    def on_open(self):
        self.update_labels()
        self._event = Clock.schedule_interval(lambda *_: self.update_labels(), 600)

    def on_dismiss(self):
        if hasattr(self, "_event"):
            self._event.cancel()

    def update_labels(self):
        w = App.get_running_app().weather
        w.refresh()
        self.wind = w.wind_speed_mph or 0
        self.wave = w.sig_wave_ft or 0
        self.temp = w.air_temp_f or 0
