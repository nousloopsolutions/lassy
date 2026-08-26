import shutil
from pathlib import Path

import pytest


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Temp repo root with real config files plus the invalid-profile fixture."""
    real_root = Path(__file__).resolve().parent.parent.parent
    shutil.copytree(real_root / "config", tmp_path / "config")
    invalid = real_root / "tests" / "fixtures" / "config" / "invalid-public-ollama.yaml"
    shutil.copy(invalid, tmp_path / "config" / "profiles" / "invalid-public-ollama.yaml")
    return tmp_path
