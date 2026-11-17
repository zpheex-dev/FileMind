"""Surface Python errors in Qt slots as test failures."""

import sys

import pytest


@pytest.fixture(autouse=True)
def fail_on_unhandled_exception(monkeypatch):
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda kind, value, traceback: errors.append(value))
    yield
    assert not errors, f"Unhandled callback exception(s): {errors}"
