from kivy.uix.popup import Popup  # type: ignore
from kivy.properties import StringProperty, ListProperty  # type: ignore
from kivy.factory import Factory  # type: ignore

from core import db

class LogCatchPopup(Popup):
    init_bait_text    = StringProperty("Select Bait")
    bait_choices      = ListProperty()
    init_species_text = StringProperty("Select Species")
    species_choices   = ListProperty()

    def on_open(self):
        self.species_choices = db.distinct_species() or ["Bass", "Perch", "Walleye"]
        self.bait_choices    = db.distinct_baits()    or ["Crankbait", "Worm", "Minnow"]

Factory.register("LogCatchPopup", cls=LogCatchPopup)
