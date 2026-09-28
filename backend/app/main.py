import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import settings
from app.bus import EventBus
from app.pipeline import Pipeline
from app.api.routes import router as api_router, init_routes
from app.api.ws import ws_router, init_ws

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("main")

# Instantiate shared components
bus = EventBus(ring_buffer_size=settings.RING_BUFFER_SIZE)
pipeline = Pipeline(config=settings, bus=bus)

# Inject components into API routers
init_routes(pipeline=pipeline, bus=bus)
init_ws(pipeline=pipeline, bus=bus)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Log Anomaly Detector Backend...")
    # Ensure data directory exists
    log_dir = os.path.dirname(os.path.abspath(settings.LOG_FILE_PATH))
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    await pipeline.start()
    yield
    logger.info("Shutting down Log Anomaly Detector Backend...")
    await pipeline.stop()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Real-Time Log Anomaly Detector",
        description="High-Throughput Log Anomaly Detection with Real-Time WebSockets and AWS Integration",
        version="2.0.0",
        lifespan=lifespan
    )

    # Configure CORS (wildcard + credentials is invalid in browsers)
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    use_wildcard = "*" in origins or not origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if use_wildcard else origins,
        allow_credentials=not use_wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(api_router)
    app.include_router(ws_router)

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
