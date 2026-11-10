#!/usr/bin/env python3
"""Sincronização por linha de comando — ideal para rodar via cron no VPS.

Uso:
    python -m scripts.sync            # sincroniza e-mail + Pluggy (o que estiver configurado)
    python scripts/sync.py

Exemplo de cron (a cada 6 horas):
    0 */6 * * * cd /app && /usr/local/bin/python -m scripts.sync >> /app/data/sync.log 2>&1
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.sync import run_sync  # noqa: E402


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        report = run_sync(db)
    finally:
        db.close()
    print(
        f"[sync] fontes={report.sources} importadas={report.inserted} "
        f"duplicadas={report.skipped} contas={report.accounts}"
    )
    for err in report.errors:
        print(f"[sync][erro] {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
