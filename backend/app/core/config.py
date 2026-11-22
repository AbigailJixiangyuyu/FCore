from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parents[3]
    service_name: str = "temporal-graph-demo-api"
    version: str = "0.1.0"

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def models_dir(self) -> Path:
        return self.project_root / "models"

    @property
    def exports_dir(self) -> Path:
        return self.project_root / "exports"

    @property
    def frontend_dist_dir(self) -> Path:
        return self.project_root / "frontend" / "dist"

    @property
    def parallel_core_binary(self) -> Path:
        return self.project_root / "backend" / ".native" / "kcore-adapter"
