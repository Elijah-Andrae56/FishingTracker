from kivy.uix.screenmanager import Screen # type: ignore
from kivy.clock import Clock# type: ignore
from kivy.app import App # type: ignore

class TrackScreen(Screen):
    def on_enter(self):
        """Called each time we navigate to the Track screen."""
        app = App.get_running_app()
        # live‑update the speed label
        self._gps_cb = app.gps.subscribe(
            lambda lat, lon, spd:
                setattr(self.ids.speed_lbl, "text", f"{spd:5.2f} kn")
        )
        # refresh buoy data every 30 min
        self._wx_event = Clock.schedule_interval(self.update_wave, 1800)
        self.update_wave()   # update immediately

    def on_leave(self):
        """Unhook callbacks so they don't run while we're on other screens."""
        if self._gps_cb:
            App.get_running_app().gps.unsubscribe(self._gps_cb)
        if self._wx_event:
            self._wx_event.cancel()

    def update_wave(self, *_):
        w = App.get_running_app().weather
        w.refresh()
        self.ids.wave_lbl.text = (
            f"Wind {w.wind_speed_mph or '–'} mph\n"
            f"Sig Wave {w.sig_wave_ft or '–'} ft"
        )
