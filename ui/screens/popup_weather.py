from kivy.uix.popup import Popup  # type: ignore
from kivy.properties import NumericProperty  # type: ignore
from kivy.clock import Clock  # type: ignore
from kivy.app import App  # type: ignore

class WeatherPopup(Popup):
    wind  = NumericProperty(0)
    wave  = NumericProperty(0)
    temp  = NumericProperty(0)

    def on_open(self):
        # paint immediately from cached values (no network)
        self._paint_from_cache()
        # repaint every 30 min while open (does NOT fetch)
        self._paint_event = Clock.schedule_interval(lambda *_: self._paint_from_cache(), 1800)
        # auto-repaint when the background fetch completes
        app = App.get_running_app()
        self._wx_old_hook = getattr(app.weather, "_on_refresh", None)
        app.weather.set_refresh_hook(lambda _w: self._paint_from_cache())

    def on_dismiss(self):
        if hasattr(self, "_paint_event"):
            self._paint_event.cancel()
        app = App.get_running_app()
        if hasattr(self, "_wx_old_hook") and self._wx_old_hook:
            app.weather.set_refresh_hook(self._wx_old_hook)

    def _paint_from_cache(self):
        w = App.get_running_app().weather
        self.wind = (w.wind_speed_mph or 0)
        self.wave = (w.sig_wave_ft or 0)
        self.temp = (w.air_temp_f or 0)

    def refresh_now(self):
        # manual refresh: run network in background; repaint on completion
        btn = self.ids.refresh_btn
        btn.disabled = True
        btn.text = "Refreshing…"

        def _done(_w):
            self._paint_from_cache()
            btn.disabled = False
            btn.text = "Refresh now"

        App.get_running_app().weather.refresh(force=True, callback=_done)
