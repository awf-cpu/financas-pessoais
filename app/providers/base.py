"""Tipos comuns da camada de conexão.

Toda origem de dados (Pluggy, OFX, CSV, PDF) normaliza para estes dataclasses,
de modo que o resto do sistema (persistência, categorização, análise) não
precisa saber de onde o dado veio.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date


@dataclass
class RawTransaction:
    date: date
    description: str
    amount: float  # negativo = saída; positivo = entrada
    currency: str = "BRL"
    external_id: str | None = None

    def fingerprint(self) -> str:
        """Hash determinístico para deduplicação entre importações."""
        base = f"{self.date.isoformat()}|{round(self.amount, 2)}|{self.description.strip().lower()}"
        if self.external_id:
            base = f"id:{self.external_id}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()


@dataclass
class RawAccount:
    name: str
    type: str = "CHECKING"  # CHECKING | CREDIT | SAVINGS
    currency: str = "BRL"
    balance: float = 0.0
    external_id: str | None = None
    transactions: list[RawTransaction] = field(default_factory=list)
