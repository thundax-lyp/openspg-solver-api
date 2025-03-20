from fastapi import FastAPI

from app.routes.app_routes import mount_routes as mount_app_routes
from app.openspg.api.openai_api import mount_routes as mount_openai_routes


def mount_all_routes(app: FastAPI, args):
    """
    Mount all routes in this package to the provided application.
    """
    mount_app_routes(app, args)
    mount_openai_routes(app, args)

    return app
