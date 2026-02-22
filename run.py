from __future__ import annotations

from led_matrix_api import create_app
from led_matrix_api.config import Settings

if __name__ == "__main__":
    settings = Settings.from_env()
    app = create_app(settings=settings)
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
