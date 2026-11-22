"""Adapt model state updates to the snapshot files used by the demo."""

from dataclasses import dataclass
from types import ModuleType

from . import artifacts as zebra_artifacts
from .model import METHOD as ZEBRA_METHOD


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


ZEBRA = ModelAdapter("Zebra", ZEBRA_METHOD, zebra_artifacts, event_stream=True)
