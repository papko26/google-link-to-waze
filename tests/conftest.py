import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import gtw  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    # args is normally created in __main__
    monkeypatch.setattr(gtw, "args", types.SimpleNamespace(gcp_maps_api_key="test-key"), raising=False)
    return gtw.app.test_client()
