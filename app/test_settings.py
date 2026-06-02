"""Django settings used by pytest.

The repository's default ``.env`` points at preprod. Pytest needs the local
test database instead, so load ``env-test`` before importing normal settings.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / "env-test", override=False)

from app.settings import *  # noqa: F401,F403,E402
