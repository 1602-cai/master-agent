"""Route assembly — builds the FastAPI app from modular routers."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes.deps import TEMPLATES_DIR, CUSTOM_TEMPLATES_DIR, runtime
from routes.upload import router as upload_router
from routes.templates import router as templates_router
from routes.jobs import router as jobs_router
from routes.projects import router as projects_router
from routes.settings import router as settings_router
from routes.ws import router as ws_router
from routes.skills import router as skills_router


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Harness", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static mounts
    if TEMPLATES_DIR.exists():
        app.mount("/static/templates", StaticFiles(directory=str(TEMPLATES_DIR)), name="templates_static")
    CUSTOM_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static/custom_templates", StaticFiles(directory=str(CUSTOM_TEMPLATES_DIR)), name="custom_templates_static")

    # Routers
    app.include_router(upload_router)
    app.include_router(templates_router)
    app.include_router(jobs_router)
    app.include_router(projects_router)
    app.include_router(settings_router)
    app.include_router(skills_router)
    app.include_router(ws_router)

    # Startup hook — recover stuck jobs
    @app.on_event("startup")
    async def _recover_stuck_jobs():
        import logging
        log = logging.getLogger("harness.startup")
        try:
            for j in runtime().list_jobs():
                if j.get("status") == "running":
                    jid = j["job_id"]
                    log.warning("Recovering stuck job %s: marking as failed", jid)
                    await runtime().jobs.async_update(
                        jid, status="failed",
                        error="服务重启导致任务中断，请重新生成",
                    )
        except Exception as e:
            log.error("Failed to recover stuck jobs: %s", e)

    return app
