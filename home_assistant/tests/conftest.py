"""Run from the home_assistant/ directory:  pip install pytest-homeassistant-custom-component && pytest tests"""
import pathlib

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

# pytest-homeassistant-custom-component ships its own `custom_components` package; add ours to its search path
import custom_components  # noqa: E402

custom_components.__path__.append(str(pathlib.Path(__file__).resolve().parents[1] / "custom_components"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
