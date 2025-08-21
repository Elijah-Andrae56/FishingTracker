from kivy.uix.popup import Popup # type: ignore
from kivy.properties import NumericProperty # type: ignore
from kivy.clock import Clock # type: ignore
from kivy.app import App # type: ignore

class WeatherPopup(Popup):
    wind  = NumericProperty(0)
    wave  = NumericProperty(0)
    temp  = NumericProperty(0)

    def on_open(self):
        self.repaint()

    def repaint(self):
        app = App.get_running_app()
        w   = app.weather
        # Use your units helper for display
        wind_txt = app.units.fmt("speed", w.wind_speed_mph, source="mph", precision=0)
        wave_txt = app.units.fmt("wave",  w.sig_wave_ft,    source="ft",  precision=1)
        self.ids.wind_lbl.text = f"Wind: {wind_txt}"
        self.ids.wave_lbl.text = f"Sig Wave: {wave_txt}"

    def refresh_now(self):
        # Disable the button while we fetch
        btn = self.ids.refresh_btn
        btn.disabled = True
        btn.text = "Refreshing…"

        def _done(_w):
            # Back on UI thread: repaint and re-enable
            self.repaint()
            btn.disabled = False
            btn.text = "Refresh now"

        App.get_running_app().weather.refresh(force=True, callback=_done)

    def on_dismiss(self):
        if hasattr(self, "_event"):
            self._event.cancel()

    def update_labels(self):
        w = App.get_running_app().weather
        w.refresh()
        self.wind = w.wind_speed_mph or 0
        self.wave = w.sig_wave_ft or 0
        self.temp = w.air_temp_f or 0
