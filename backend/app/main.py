from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.core.config import Settings
from app.services.parallel_core import CoreSolver, ParallelCoreCache
from app.services.reports.provider import ReportClient
from app.services.snapshot_updates import SnapshotSessions


def create_app(
    settings: Settings | None = None, *, core_solver: CoreSolver | None = None
) -> FastAPI:
    settings = settings or Settings()
    application = FastAPI(
        title="Temporal Graph Analysis Demo API",
        description="Access local interaction data, snapshots, and temporal graph analysis.",
        version=settings.version,
    )
    application.state.settings = settings
    application.state.snapshot_sessions = SnapshotSessions(settings.data_dir)
    application.state.report_client = ReportClient.from_env(settings.project_root / "backend" / ".env")
    application.state.parallel_core = ParallelCoreCache(settings.parallel_core_binary, core_solver)
    application.include_router(router, prefix="/api")

    # API 与文档先注册，静态文件不会覆盖它们。
    if (settings.frontend_dist_dir / "index.html").is_file():
        application.mount(
            "/",
            StaticFiles(directory=settings.frontend_dist_dir, html=True),
            name="frontend",
        )

    return application


app = create_app()
