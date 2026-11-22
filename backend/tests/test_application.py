from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(Settings(project_root=tmp_path))) as test_client:
        yield test_client


def test_api_starts_without_frontend_build(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "temporal-graph-demo-api",
        "version": "0.1.0",
    }
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_static_hosting_preserves_api_and_missing_route_status(tmp_path: Path) -> None:
    settings = Settings(project_root=tmp_path)
    settings.frontend_dist_dir.mkdir(parents=True)
    (settings.frontend_dist_dir / "index.html").write_text(
        "<!doctype html><title>Workbench</title>",
        encoding="utf-8",
    )
    asset_dir = settings.frontend_dist_dir / "assets"
    asset_dir.mkdir()
    (asset_dir / "app.js").write_text("console.log('workbench')", encoding="utf-8")

    with TestClient(create_app(settings)) as client:
        assert "Workbench" in client.get("/").text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/docs").status_code == 200
        assert client.get("/api/unknown").status_code == 404
        assert client.get("/assets/missing.js").status_code == 404
