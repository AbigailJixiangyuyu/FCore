from functools import partial

import pytest

from algorithms.core.queries import core_numbers
from app.main import create_app


@pytest.fixture(scope="module")
def app_with_test_core():
    """Exercise the HTTP contract without requiring a built WSL adapter."""
    return partial(create_app, core_solver=core_numbers)
