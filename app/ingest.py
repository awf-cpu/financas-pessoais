"""Persistência de dados normalizados: grava RawAccount no banco.

Responsável por:
  - criar/achar a Connection e a Account,
  - deduplicar transações (por fingerprint),
  - categorizar cada transação nova.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categorize import categorize
from .models import Account, Connection, Transaction
from .providers.base import RawAccount


@dataclass
class IngestResult:
    accounts: int = 0
    inserted: int = 0
    skipped: int = 0  # duplicadas


def ingest_accounts(
    db: Session,
    raw_accounts: list[RawAccount],
    provider: str,
    institution: str = "",
    external_item_id: str | None = None,
) -> IngestResult:
    result = IngestResult()
    if not raw_accounts:
        return result

    connection = _get_or_create_connection(db, provider, institution, external_item_id)

    for raw in raw_accounts:
        result.accounts += 1
        account = _get_or_create_account(db, connection, raw)
        # fingerprints já existentes nesta conta (evita duplicar)
        existing = set(
            db.scalars(
                select(Transaction.fingerprint).where(Transaction.account_id == account.id)
            ).all()
        )
        for tx in raw.transactions:
            fp = tx.fingerprint()
            if fp in existing:
                result.skipped += 1
                continue
            existing.add(fp)
            cat, source = categorize(tx.description, tx.amount)
            db.add(
                Transaction(
                    account_id=account.id,
                    external_id=tx.external_id,
                    fingerprint=fp,
                    date=tx.date,
                    description=tx.description,
                    amount=tx.amount,
                    currency=tx.currency,
                    category=cat,
                    category_source=source,
                )
            )
            result.inserted += 1
        if raw.balance:
            account.balance = raw.balance

    connection.last_sync_at = datetime.utcnow()
    db.commit()
    return result


def _get_or_create_connection(
    db: Session, provider: str, institution: str, external_item_id: str | None
) -> Connection:
    stmt = select(Connection).where(Connection.provider == provider)
    if external_item_id:
        stmt = stmt.where(Connection.external_id == external_item_id)
    elif institution:
        stmt = stmt.where(Connection.institution == institution)
    conn = db.scalars(stmt).first()
    if conn is None:
        conn = Connection(
            provider=provider, institution=institution, external_id=external_item_id
        )
        db.add(conn)
        db.flush()
    return conn


def _get_or_create_account(db: Session, connection: Connection, raw: RawAccount) -> Account:
    stmt = select(Account).where(Account.connection_id == connection.id)
    if raw.external_id:
        stmt = stmt.where(Account.external_id == raw.external_id)
    else:
        stmt = stmt.where(Account.name == raw.name)
    account = db.scalars(stmt).first()
    if account is None:
        account = Account(
            connection_id=connection.id,
            external_id=raw.external_id,
            name=raw.name,
            type=raw.type,
            currency=raw.currency,
            balance=raw.balance,
        )
        db.add(account)
        db.flush()
    return account
