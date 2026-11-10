"""Orquestra a sincronização automática de todas as fontes configuradas.

Usado tanto pelo endpoint HTTP /sync quanto pelo script de cron (scripts/sync.py).
Cada fonte é opcional: só roda se estiver configurada no .env.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .config import get_settings
from .ingest import IngestResult, ingest_accounts
from .providers import fileimport


@dataclass
class SyncReport:
    sources: list[str] = field(default_factory=list)
    inserted: int = 0
    skipped: int = 0
    accounts: int = 0
    errors: list[str] = field(default_factory=list)

    def _add(self, source: str, r: IngestResult) -> None:
        if source not in self.sources:
            self.sources.append(source)
        self.inserted += r.inserted
        self.skipped += r.skipped
        self.accounts += r.accounts


def run_sync(db: Session) -> SyncReport:
    report = SyncReport()
    _sync_email(db, report)
    _sync_pluggy(db, report)
    return report


def _sync_email(db: Session, report: SyncReport) -> None:
    s = get_settings()
    if not s.imap_enabled:
        return
    try:
        from .providers.email_imap import fetch_statement_attachments

        for att in fetch_statement_attachments():
            try:
                raw = fileimport.import_file(att.filename, att.content)
            except Exception as e:  # anexo que não dá pra importar: ignora
                report.errors.append(f"e-mail/{att.filename}: {e}")
                continue
            if not raw.transactions:
                continue
            r = ingest_accounts(
                db, [raw], provider="fileimport", institution=f"email:{att.sender[:60]}"
            )
            report._add("email", r)
    except Exception as e:
        report.errors.append(f"email: {e}")


def _sync_pluggy(db: Session, report: SyncReport) -> None:
    s = get_settings()
    if not s.pluggy_enabled:
        return
    try:
        from sqlalchemy import select

        from .models import Connection
        from .providers.pluggy import PluggyClient

        item_ids = [
            c.external_id
            for c in db.scalars(
                select(Connection).where(Connection.provider == "pluggy")
            ).all()
            if c.external_id
        ]
        if not item_ids:
            return
        with PluggyClient() as client:
            for item_id in item_ids:
                try:
                    accounts = client.fetch_item_as_accounts(item_id)
                    r = ingest_accounts(
                        db, accounts, provider="pluggy", external_item_id=item_id
                    )
                    report._add("pluggy", r)
                except Exception as e:
                    report.errors.append(f"pluggy/{item_id}: {e}")
    except Exception as e:
        report.errors.append(f"pluggy: {e}")
