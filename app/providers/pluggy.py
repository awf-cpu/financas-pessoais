"""Cliente da API Pluggy (Open Finance Brasil).

Fluxo:
  1. `authenticate()` troca client_id/secret por um apiKey de curta duração.
  2. O usuário conecta o banco pelo **Pluggy Connect** (widget no navegador),
     gerando um `itemId`. Veja `create_connect_token()`.
  3. `list_accounts(item_id)` e `list_transactions(account_id)` puxam os dados.

Docs: https://docs.pluggy.ai  (o domínio pode precisar ser liberado na rede).
Este módulo NÃO guarda credenciais; elas vêm do .env via Settings.
"""
from __future__ import annotations

from datetime import date, datetime

import httpx

from ..config import get_settings
from .base import RawAccount, RawTransaction

_TYPE_MAP = {
    "BANK": "CHECKING",
    "CREDIT": "CREDIT",
}


class PluggyError(RuntimeError):
    pass


class PluggyClient:
    def __init__(self, timeout: float = 30.0) -> None:
        s = get_settings()
        if not s.pluggy_enabled:
            raise PluggyError(
                "Pluggy não configurado: defina PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET no .env."
            )
        self._client_id = s.pluggy_client_id
        self._client_secret = s.pluggy_client_secret
        self._base = s.pluggy_base_url.rstrip("/")
        self._api_key: str | None = None
        self._http = httpx.Client(base_url=self._base, timeout=timeout)

    # -- autenticação -------------------------------------------------------
    def authenticate(self) -> str:
        r = self._http.post(
            "/auth",
            json={"clientId": self._client_id, "clientSecret": self._client_secret},
        )
        if r.status_code != 200:
            raise PluggyError(f"Falha na autenticação Pluggy: {r.status_code} {r.text}")
        self._api_key = r.json()["apiKey"]
        return self._api_key

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            self.authenticate()
        return {"X-API-KEY": self._api_key or ""}

    # -- Connect (widget) ---------------------------------------------------
    def create_connect_token(self, item_id: str | None = None) -> str:
        """Gera um connectToken para abrir o Pluggy Connect no navegador."""
        payload = {"itemId": item_id} if item_id else {}
        r = self._http.post("/connect_token", headers=self._headers(), json=payload)
        if r.status_code not in (200, 201):
            raise PluggyError(f"Falha ao gerar connect_token: {r.status_code} {r.text}")
        return r.json()["accessToken"]

    # -- leitura de dados ---------------------------------------------------
    def get_item(self, item_id: str) -> dict:
        r = self._http.get(f"/items/{item_id}", headers=self._headers())
        if r.status_code != 200:
            raise PluggyError(f"Falha ao buscar item {item_id}: {r.status_code} {r.text}")
        return r.json()

    def list_accounts(self, item_id: str) -> list[dict]:
        r = self._http.get(
            "/accounts", headers=self._headers(), params={"itemId": item_id}
        )
        if r.status_code != 200:
            raise PluggyError(f"Falha ao listar contas: {r.status_code} {r.text}")
        return r.json().get("results", [])

    def list_transactions(
        self, account_id: str, date_from: date | None = None, page_size: int = 500
    ) -> list[dict]:
        results: list[dict] = []
        page = 1
        while True:
            params: dict[str, object] = {"accountId": account_id, "pageSize": page_size, "page": page}
            if date_from:
                params["from"] = date_from.isoformat()
            r = self._http.get("/transactions", headers=self._headers(), params=params)
            if r.status_code != 200:
                raise PluggyError(f"Falha ao listar transações: {r.status_code} {r.text}")
            body = r.json()
            results.extend(body.get("results", []))
            total_pages = body.get("totalPages", 1)
            if page >= total_pages:
                break
            page += 1
        return results

    # -- normalização -------------------------------------------------------
    def fetch_item_as_accounts(
        self, item_id: str, date_from: date | None = None
    ) -> list[RawAccount]:
        """Puxa contas + transações de um item e normaliza para RawAccount."""
        accounts: list[RawAccount] = []
        for acc in self.list_accounts(item_id):
            raw = RawAccount(
                name=acc.get("name") or acc.get("marketingName") or "Conta",
                type=_TYPE_MAP.get(acc.get("type", ""), "CHECKING"),
                currency=acc.get("currencyCode", "BRL"),
                balance=float(acc.get("balance") or 0.0),
                external_id=acc.get("id"),
            )
            for tx in self.list_transactions(acc["id"], date_from=date_from):
                raw.transactions.append(_normalize_tx(tx))
            accounts.append(raw)
        return accounts

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "PluggyClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _normalize_tx(tx: dict) -> RawTransaction:
    raw_date = tx.get("date", "")
    try:
        d = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        d = date.today()
    # Na Pluggy, amount já vem com sinal (negativo = débito).
    amount = float(tx.get("amount", 0.0))
    return RawTransaction(
        date=d,
        description=tx.get("description") or tx.get("descriptionRaw") or "",
        amount=amount,
        currency=tx.get("currencyCode", "BRL"),
        external_id=tx.get("id"),
    )
