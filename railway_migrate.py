"""Railway pre-deploy: migratsiya oldidan diagnostika va `alembic upgrade`.

Pre-deploy bosqichida log'da nimayanglish kerak:
- DATABASE_URL o'rnatilganmi
- yakuniy database_url (parol maskalangan)
- shundan keyin migratsiya ishga tushadi.
"""

import os
import re
import sys

from alembic import command
from alembic.config import Config

from app.core.config import settings


def mask(url: str) -> str:
    return re.sub(r"(://[^:]*:)([^@]+)(@)", r"\1***@", url)


def main() -> int:
    raw = os.environ.get("DATABASE_URL") or ""
    print(
        "DATABASE_URL env: " + ("o'rnatilgan" if raw else "YO'Q (not set)"),
        flush=True,
    )
    if raw:
        print("env prefix: " + raw.split(":", 2)[0], flush=True)
    print("database_url (masked): " + mask(settings.database_url), flush=True)
    try:
        command.upgrade(Config("alembic.ini"), "head")
    except Exception as exc:  # noqa: BLE001
        print("MIGRATION ERROR:", type(exc).__name__, str(exc), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
