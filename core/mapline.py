# mapline.py  

from kivy.uix.widget import Widget          # type: ignore
from kivy.graphics import Color, Line       # type: ignore
from kivy_garden.mapview import MapView     # type: ignore

class MapLine(Widget):
    """Draws a red poly-line on top of a MapView."""
    def __init__(self, mapview: MapView, **kwargs):
        super().__init__(**kwargs)
        self.mapview = mapview
        self.points_latlon: list[tuple[float, float]] = []

        # Redraw whenever the map pans / zooms / resizes
        self.bind(pos=self._redraw, size=self._redraw)
        self.mapview.bind(center=self._redraw, zoom=self._redraw)

    # Public -----------------------------------------------------------------
    def add_point(self, lat: float, lon: float) -> None:
        self.points_latlon.append((lat, lon))
        self._redraw()

    # Internal ---------------------------------------------------------------
    def _redraw(self, *_) -> None:
        self.canvas.clear()
        if len(self.points_latlon) < 2:
            return

        with self.canvas:
            Color(1, 0, 0, 0.9)              # semi-opaque red
            pts = []
            for lat, lon in self.points_latlon:
                x, y = self.mapview.get_window_xy_from(lat, lon,
                                                       self.mapview.zoom)
                pts += [x, y]
            Line(points=pts, width=2)
