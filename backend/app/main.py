from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import cricket, health, imports
from app.core.config import get_settings
from app.db.session import create_db_and_tables


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(cricket.router)
    app.include_router(imports.router)

    @app.on_event("startup")
    def on_startup() -> None:
        create_db_and_tables()

    return app


app = create_app()

