from kivy.uix.screenmanager import Screen # type: ignore
from core import db 
from kivy.app import App # type: ignore

class HomeScreen(Screen):
    def start_trip(self):
        app = App.get_running_app()
        app.current_session = db.start_session()
        self.manager.current = "track"
