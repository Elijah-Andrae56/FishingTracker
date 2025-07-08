# ui/main.py  – revised
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.label import Label

from core.gps_utils import GPSTracker
from core.waves     import Weather


class Root(TabbedPanel):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.do_default_tab = False

        # ── data back-ends ────────────────────────────────────────────
        self.gps     = GPSTracker()
        self.weather = Weather()

        # ── UI setup ─────────────────────────────────────────────────
        self.lbl_speed = Label(font_size="20sp")
        self._add_tab("Track", self.lbl_speed)

        self.lbl_wave  = Label(font_size="20sp")
        self._add_tab("Wave Conditions",  self.lbl_wave)

        self._add_tab("Logbook", Label(text="Coming soon"))

        # ── start background tasks ───────────────────────────────────
        self.gps.start()
        Clock.schedule_interval(self._update_speed,   1.0)     # every sec
        Clock.schedule_once(   self._update_weather,  0)       # now
        Clock.schedule_interval(self._update_weather, 1800)    # 30 min

    # ---------- helpers ---------------------------------------------
    def _add_tab(self, title, widget):
        tab       = TabbedPanelItem(text=title)
        tab.add_widget(widget)
        self.add_widget(tab)

    # ---------- periodic callbacks ----------------------------------
    def _update_speed(self, *_):
        self.lbl_speed.text = f"Speed (kn): {self.gps.speed_knots:5.2f}"

    def _update_weather(self, *_):
        try:
            self.weather.refresh()
            w  = self.weather
            ts = w.time_utc.strftime("%H:%MZ") if w.time_utc else "–"

            # grace-fully handle the rare None result
            f_or_dash = lambda v, fmt: (fmt % v) if v is not None else "-"
            self.lbl_wave.text  = (
                f"Time: {ts} — \n"
                f"Wind Speed {f_or_dash(w.wind_speed_mph,                           '%.2f')} mph  \n"
                f"Wind Direction {f_or_dash(w.wind_direction_deg,                   '%.2f')} \n"
                f"Average Wave Height {f_or_dash(w.sig_wave_ft,                     '%.2f')} ft  \n"
                f"Max Wave Height {f_or_dash(w.max_wave_ft,                         '%.2f')} ft \n "
                f"Average Wave Direction {f_or_dash(w.max_wave_ft,                  '%.2f')} \n "
                f"Dominant wave period {f_or_dash(w.dominant_wave_direction_deg,    '%.2f')} s \n "
                f"Air Temp {f_or_dash(w.air_temp_f,                                 '%.1f')} f"
            )
        except Exception as e:
            self.lbl_wave.text = "Buoy: error"
            # optional:  print(e)  # shows in `adb logcat | grep python`

class FishTrackerApp(App):
    def build(self):
        return Root()

if __name__ == "__main__":
    FishTrackerApp().run()
