"""Shared, dataset-specific defaults for the web forms and omitted API fields."""

import json
from pathlib import Path
from typing import Any

QUERY_DEFAULTS = json.loads(
    (Path(__file__).resolve().parents[3] / "config/query-defaults.json").read_text(
        encoding="utf-8"
    )
)


def query_defaults(dataset_id: str | None, method: str | None) -> dict:
    if not isinstance(method, str):
        return {}
    profile = QUERY_DEFAULTS["synthetic-small"]
    if isinstance(dataset_id, str):
        profile = QUERY_DEFAULTS.get(dataset_id, profile)
    return dict(profile.get(method, {}))


def apply_query_defaults(value: Any, method: str) -> Any:
    if not isinstance(value, dict):
        return value
    dataset_id = value.get("dataset_id")
    defaults = query_defaults(dataset_id, method)
    if method == "burst":
        # Omitted accounts continue to request the global bursting core.
        defaults.pop("account", None)
    parameters = {**defaults, **value}
    if method in ("periodic", "durable", "burst", "future_core"):
        account = parameters.get("account")
        if isinstance(account, str):
            # Built-in query forms already normalize whitespace, but uploaded IDs are literal.
            if not account.strip() or (isinstance(dataset_id, str) and dataset_id in QUERY_DEFAULTS):
                parameters["account"] = account.strip()
    return parameters
