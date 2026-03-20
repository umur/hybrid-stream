"""Shared fixtures for AODE tests. All external deps are mocked."""
import pytest


@pytest.fixture
def aode_config():
    """Return an AODEConfig with defaults (no real env vars)."""
    from aode.aode.config import AODEConfig
    return AODEConfig()
