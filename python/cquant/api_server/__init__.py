"""cquant.api_server — FastAPI service for cQuant research platform."""

from cquant.api_server.app import create_app

__all__ = ["create_app"]
