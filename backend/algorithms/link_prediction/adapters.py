"""Small model registry; each encoder retains its own artifact and state format."""

from dataclasses import dataclass
from types import ModuleType

from . import artifacts as zebra_artifacts
from .model import METHOD as ZEBRA_METHOD
from .undergs import artifacts as undergs_artifacts
from .undergs.model import METHOD as UNDERGS_METHOD


@dataclass(frozen=True)
class ModelAdapter:
    name: str
    method: str
    artifacts: ModuleType
    event_stream: bool = False

    def advance(self, model, state, window):
        if self.event_stream:
            model.advance(state, window.events)
        else:
            model.advance_window(state, window)


MODELS = {
    "zebra": ModelAdapter("Zebra", ZEBRA_METHOD, zebra_artifacts, event_stream=True),
    "undergs": ModelAdapter("UnderGS", UNDERGS_METHOD, undergs_artifacts),
}
