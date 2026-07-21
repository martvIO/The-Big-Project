import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_app_module_imports_without_database_available() -> None:
    """`import app.main` builds the default resolver (and lazily the engine
    singleton) at import time. This must never require a reachable database or
    a DATABASE_URL — otherwise every fast test run and tooling import breaks."""
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "APP_ENV")}
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
        env=env,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
