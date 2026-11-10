"""Importadores de extratos/faturas: OFX, CSV e PDF.

Todos retornam `RawAccount` com suas `RawTransaction`, prontos para persistir.
Dependências pesadas (ofxparse, pdfplumber) são importadas de forma tardia,
para o app subir mesmo sem elas instaladas.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime

from .base import RawAccount, RawTransaction


# --------------------------------------------------------------------------
# OFX  (formato padrão de extrato — praticamente todo banco BR exporta)
# --------------------------------------------------------------------------
def import_ofx(content: bytes, account_name: str = "Conta (OFX)") -> RawAccount:
    from ofxparse import OfxParser  # import tardio

    ofx = OfxParser.parse(io.BytesIO(content))
    acc_type = "CHECKING"
    balance = 0.0
    name = account_name
    txs: list[RawTransaction] = []

    account = ofx.account if hasattr(ofx, "account") else None
    accounts = getattr(ofx, "accounts", None) or ([account] if account else [])
    for acc in accounts:
        statement = getattr(acc, "statement", None)
        if statement is None:
            continue
        balance = float(getattr(statement, "balance", 0.0) or 0.0)
        # ofxparse: `type` é um enum (AccountType), `account_type` é string crua.
        a_type = str(getattr(acc, "account_type", "") or "").upper()
        type_enum = str(getattr(acc, "type", "") or "").upper()
        if "CREDIT" in a_type or "CREDIT" in type_enum:
            acc_type = "CREDIT"
        for t in getattr(statement, "transactions", []):
            txs.append(
                RawTransaction(
                    date=t.date.date() if isinstance(t.date, datetime) else t.date,
                    description=(t.memo or t.payee or "").strip(),
                    amount=float(t.amount),
                    external_id=getattr(t, "id", None),
                )
            )
    return RawAccount(name=name, type=acc_type, balance=balance, transactions=txs)


# --------------------------------------------------------------------------
# CSV  (heurística tolerante: detecta colunas de data, descrição e valor)
# --------------------------------------------------------------------------
_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y")
_DATE_KEYS = ("data", "date", "dt", "lançamento", "lancamento")
_DESC_KEYS = ("descrição", "descricao", "description", "histórico", "historico",
              "lançamento", "lancamento", "memo", "detalhe", "estabelecimento", "title")
# Obs.: não incluir "crédito/débito" aqui — são tratados como colunas separadas
# mais abaixo; se entrassem, colidiriam com a detecção da coluna única de valor.
_AMOUNT_KEYS = ("valor", "amount", "montante", "value", "quantia")


def _parse_date(value: str) -> date | None:
    value = (value or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(value: str) -> float | None:
    """Converte '1.234,56', 'R$ -1.234,56', '(123,45)' etc. em float."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.replace("R$", "").replace("(", "").replace(")", "").strip()
    s = re.sub(r"\s+", "", s)
    if "," in s and "." in s:          # 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                      # 1234,56 -> 1234.56
        s = s.replace(",", ".")
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


def _find_key(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    lower = {f.lower().strip(): f for f in fieldnames}
    for cand in candidates:
        for key, original in lower.items():
            if cand in key:
                return original
    return None


def import_csv(content: bytes, account_name: str = "Conta (CSV)") -> RawAccount:
    text = content.decode("utf-8-sig", errors="replace")
    # Detecta separador (vírgula ou ponto-e-vírgula — comum no Brasil).
    sample = text[:2048]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fields = reader.fieldnames or []

    date_key = _find_key(fields, _DATE_KEYS)
    desc_key = _find_key(fields, _DESC_KEYS)
    amount_key = _find_key(fields, _AMOUNT_KEYS)
    # Colunas separadas de débito/crédito (alguns bancos)
    debit_key = _find_key(fields, ("débito", "debito", "saída", "saida", "debit"))
    credit_key = _find_key(fields, ("crédito", "credito", "entrada", "credit"))

    txs: list[RawTransaction] = []
    for row in reader:
        d = _parse_date(row.get(date_key, "")) if date_key else None
        if not d:
            continue
        desc = (row.get(desc_key, "") if desc_key else "").strip()
        amount: float | None = None
        # Prioriza colunas separadas de débito/crédito quando existirem.
        if debit_key or credit_key:
            deb = _parse_amount(row.get(debit_key, "")) if debit_key else None
            cre = _parse_amount(row.get(credit_key, "")) if credit_key else None
            if cre:
                amount = abs(cre)
            elif deb:
                amount = -abs(deb)
        elif amount_key:
            amount = _parse_amount(row.get(amount_key, ""))
        if amount is None:
            continue
        txs.append(RawTransaction(date=d, description=desc, amount=amount))
    return RawAccount(name=account_name, type="CHECKING", transactions=txs)


# --------------------------------------------------------------------------
# PDF  (faturas de cartão / extratos — extração heurística linha a linha)
# --------------------------------------------------------------------------
# Linha típica de fatura:  "05/11  NETFLIX.COM            39,90"
_PDF_LINE = re.compile(
    r"(?P<data>\d{2}/\d{2}(?:/\d{2,4})?)\s+(?P<desc>.+?)\s+"
    r"(?P<valor>-?\(?R?\$?\s?\d{1,3}(?:\.\d{3})*,\d{2}\)?)\s*$"
)


def import_pdf(content: bytes, account_name: str = "Cartão (PDF)", year: int | None = None) -> RawAccount:
    import pdfplumber  # import tardio

    year = year or date.today().year
    txs: list[RawTransaction] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                m = _PDF_LINE.search(line.strip())
                if not m:
                    continue
                d = _parse_pdf_date(m.group("data"), year)
                if not d:
                    continue
                amount = _parse_amount(m.group("valor"))
                if amount is None:
                    continue
                # Em fatura de cartão, a maioria são despesas (saídas).
                txs.append(
                    RawTransaction(
                        date=d, description=m.group("desc").strip(), amount=-abs(amount)
                    )
                )
    return RawAccount(name=account_name, type="CREDIT", transactions=txs)


def _parse_pdf_date(value: str, default_year: int) -> date | None:
    value = value.strip()
    if re.fullmatch(r"\d{2}/\d{2}", value):
        value = f"{value}/{default_year}"
    return _parse_date(value)


# --------------------------------------------------------------------------
# Dispatcher por extensão / tipo de conteúdo
# --------------------------------------------------------------------------
def import_file(filename: str, content: bytes) -> RawAccount:
    name = filename.rsplit("/", 1)[-1]
    lower = name.lower()
    stem = name.rsplit(".", 1)[0]
    if lower.endswith(".ofx") or lower.endswith(".qfx"):
        return import_ofx(content, account_name=f"{stem} (OFX)")
    if lower.endswith(".csv") or lower.endswith(".txt"):
        return import_csv(content, account_name=f"{stem} (CSV)")
    if lower.endswith(".pdf"):
        return import_pdf(content, account_name=f"{stem} (PDF)")
    raise ValueError(f"Formato não suportado: {name} (use OFX, CSV ou PDF).")
