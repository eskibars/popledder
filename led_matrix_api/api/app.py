from __future__ import annotations

from flask import Flask

from ..config import Settings
from ..ble.service import LedBleService
from .routes import make_blueprint

def create_app(*, settings: Settings | None = None) -> Flask:
    settings = settings or Settings.from_env()

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        static_url_path="/static",
    )

    ble = LedBleService(settings.device_address, settings=settings) if settings.device_address else None
    app.register_blueprint(make_blueprint(ble=ble, settings=settings))
    return app
