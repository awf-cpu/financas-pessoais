"""Modelos de dados.

Relações:
    Connection 1--N Account 1--N Transaction
Uma Connection representa um vínculo com uma instituição (via Pluggy) ou uma
origem de importação de arquivos (OFX/CSV/PDF).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))  # "pluggy" | "fileimport"
    institution: Mapped[str] = mapped_column(String(120), default="")
    # id externo (ex.: itemId da Pluggy). Nulo para importação de arquivos.
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    accounts: Mapped[list["Account"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("connection_id", "external_id", name="uq_account_ext"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("connections.id"))
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    name: Mapped[str] = mapped_column(String(120), default="Conta")
    type: Mapped[str] = mapped_column(String(32), default="CHECKING")  # CHECKING|CREDIT|SAVINGS
    currency: Mapped[str] = mapped_column(String(8), default="BRL")
    balance: Mapped[float] = mapped_column(Float, default=0.0)

    connection: Mapped["Connection"] = relationship(back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"
    # Dedup: evita inserir a mesma transação duas vezes.
    __table_args__ = (
        UniqueConstraint("account_id", "fingerprint", name="uq_tx_fingerprint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # hash determinístico (data+valor+descrição) para deduplicar importações.
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)

    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(400), default="")
    # valor negativo = saída (gasto); positivo = entrada (receita)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="BRL")

    category: Mapped[str] = mapped_column(String(64), default="Não categorizado", index=True)
    category_source: Mapped[str] = mapped_column(String(16), default="rules")  # rules|llm|manual
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped["Account"] = relationship(back_populates="transactions")


class Institution(Base):
    """Instituição descoberta via relatório CCS do Registrato (Banco Central).

    Serve como "mapa" de todos os bancos onde o CPF tem relacionamento, para
    o usuário saber de onde coletar extratos. O CCS não traz saldo/extrato.
    """

    __tablename__ = "institutions"
    __table_args__ = (UniqueConstraint("name", name="uq_institution_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    relationship_start: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(32), default="registrato_ccs")
    # discovered | connected | ignored
    status: Mapped[str] = mapped_column(String(16), default="discovered")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
