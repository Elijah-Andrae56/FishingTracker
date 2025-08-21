from __future__ import annotations
from typing import Callable, Optional, Tuple

UNITS_SETTINGS_JSON = """
[
  {"type": "title", "title": "Units"},
  {"type": "options", "title": "Length",     "desc": "Display & input", "section": "units", "key": "length",   "options": ["cm", "in"]},
  {"type": "options", "title": "Weight",     "desc": "Display",         "section": "units", "key": "weight",   "options": ["kg", "lb"]},
  {"type": "options", "title": "Speed",      "desc": "Display",         "section": "units", "key": "speed",    "options": ["kph", "mph", "kn"]},
  {"type": "options", "title": "Temperature","desc": "Display",         "section": "units", "key": "temp",     "options": ["C", "F"]},
  {"type": "options", "title": "Wave height","desc": "Display",         "section": "units", "key": "wave",     "options": ["m", "ft"]},
  {"type": "options", "title": "Distance",   "desc": "Display",         "section": "units", "key": "distance", "options": ["km", "mi", "nm"]}
]
"""

# Canonical (base) units we’ll keep internally:
# length: cm, weight: kg, speed: kph, temp: C, wave: m, distance: km

_KG_PER_LB = 0.45359237
_KM_PER_MI = 1.609344
_KM_PER_NM = 1.852
_M_PER_FT  = 0.3048

class Units:
    def __init__(self, config):
        self.config = config
        self._listeners: list[Callable[[Units], None]] = []

    # ---- subscription for UI to repaint on settings change ----
    def bind(self, callback: Callable[["Units"], None]) -> None:
        self._listeners.append(callback)

    def notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb(self)
            except Exception:
                pass

    # ---- current choices ----
    def choice(self, cat: str) -> str:
        # section "units" keys must exist in App.build_config()
        return self.config.get("units", cat)

    # ---- conversions TO/FROM base ----
    def to_base(self, cat: str, x: float, *, source: Optional[str] = None) -> float:
        """Convert value x from `source` units to canonical base units."""
        u = (source or self.choice(cat)).lower()
        if cat == "length":   # base cm
            return x if u == "cm" else x * 2.54  # in -> cm
        if cat == "weight":   # base kg
            return x if u == "kg" else x * _KG_PER_LB  # lb -> kg
        if cat == "speed":    # base kph
            if u == "kph": return x
            if u == "mph": return x * _KM_PER_MI
            if u == "kn":  return x * _KM_PER_NM
        if cat == "temp":     # base C
            return x if u == "c" else (x - 32.0) * 5.0 / 9.0
        if cat == "wave":     # base m
            return x if u == "m" else x * _M_PER_FT
        if cat == "distance": # base km
            if u == "km": return x
            if u == "mi": return x * _KM_PER_MI
            if u == "nm": return x * _KM_PER_NM
        raise ValueError(f"Unsupported unit for {cat}: {u}")

    def from_base(self, cat: str, x_base: float) -> Tuple[float, str]:
        """Convert value from base units to the user-selected units; returns (value, unit_str)."""
        u = self.choice(cat).lower()
        if cat == "length":   # base cm
            return (x_base, "cm") if u == "cm" else (x_base / 2.54, "in")
        if cat == "weight":   # base kg
            return (x_base, "kg") if u == "kg" else (x_base / _KG_PER_LB, "lb")
        if cat == "speed":    # base kph
            if u == "kph": return (x_base, "kph")
            if u == "mph": return (x_base / _KM_PER_MI, "mph")
            if u == "kn":  return (x_base / _KM_PER_NM, "kn")
        if cat == "temp":     # base C
            return (x_base, "C") if u == "c" else (x_base * 9.0 / 5.0 + 32.0, "F")
        if cat == "wave":     # base m
            return (x_base, "m") if u == "m" else (x_base / _M_PER_FT, "ft")
        if cat == "distance": # base km
            if u == "km": return (x_base, "km")
            if u == "mi": return (x_base / _KM_PER_MI, "mi")
            if u == "nm": return (x_base / _KM_PER_NM, "nm")
        raise ValueError(f"Unsupported unit for {cat}: {u}")

    # ---- convenience formatters ----
    def fmt_from_base(self, cat: str, x_base: float | None, *, precision: int = 1, dash: str = "–") -> str:
        if x_base is None:
            return dash
        v, unit = self.from_base(cat, float(x_base))
        return f"{v:.{precision}f} {unit}"

    def fmt(self, cat: str, x: float | None, *, source: Optional[str] = None, precision: int = 1, dash: str = "–") -> str:
        if x is None:
            return dash
        base = self.to_base(cat, float(x), source=source)
        return self.fmt_from_base(cat, base, precision=precision, dash=dash)
