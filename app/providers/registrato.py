"""Parser do relatório CCS do Registrato (Banco Central do Brasil).

O CCS — *Relatório de Relacionamentos com Instituições Financeiras* — é obtido
gratuitamente em https://www.bcb.gov.br/cidadaniafinanceira/registrato com login
gov.br. Ele lista TODAS as instituições em que o CPF tem/teve relacionamento
(contas, poupança, contas de pagamento). **Não traz saldo nem extrato** — é um
mapa de "onde você tem conta", o ponto de partida para coletar os extratos.

Este módulo extrai, de forma tolerante, os nomes das instituições a partir do
PDF do relatório. O layout do BCB pode mudar; por isso o parser é heurístico e
você pode revisar/editar a lista no dashboard.

Observação importante: o login gov.br exige CAPTCHA/validação e NÃO deve ser
automatizado. O fluxo correto é: usuário baixa o PDF no Registrato e importa aqui.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

REGISTRATO_URL = "https://www.bcb.gov.br/cidadaniafinanceira/registrato"

# Sufixos típicos de razão social de instituições financeiras brasileiras.
_INST_HINTS = re.compile(
    r"(S\.?A\.?|S/A|BANCO|CAIXA|COOPERATIV|CORRETORA|DTVM|CTVM|"
    r"PAGAMENTOS?|CR[ÉE]DITO|FINANCEIRA|SCD|SOCIEDADE|INSTITUI[ÇC][ÃA]O|"
    r"FUNDO|LTDA|IP\b|CFI\b)",
    re.IGNORECASE,
)
# Linhas de cabeçalho/rodapé a ignorar.
_NOISE = re.compile(
    r"(banco central|registrato|relat[óo]rio|cpf\b|cnpj\b|p[áa]gina|"
    r"in[íi]cio de relacionamento|data da consulta|per[íi]odo|"
    r"sistema financeiro|munic[íi]pio|emiss[ãa]o|www\.|https?:)",
    re.IGNORECASE,
)
_DATE = re.compile(r"\d{2}/\d{2}/\d{4}")


@dataclass
class DiscoveredInstitution:
    name: str
    relationship_start: str = ""


def parse_ccs_pdf(content: bytes) -> list[DiscoveredInstitution]:
    import pdfplumber  # import tardio

    found: dict[str, DiscoveredInstitution] = {}
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        # 1) Tenta extrair de tabelas (layout mais recente do CCS).
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    _consider_row(row, found)
            # 2) Fallback: linhas de texto corrido.
            for line in (page.extract_text() or "").splitlines():
                _consider_line(line, found)
    return list(found.values())


def _consider_row(row: list, found: dict) -> None:
    cells = [(c or "").strip() for c in row if c]
    if not cells:
        return
    name = max(cells, key=len)
    if _looks_like_institution(name):
        date = next((c for c in cells if _DATE.search(c)), "")
        _add(found, name, date)


def _consider_line(line: str, found: dict) -> None:
    line = line.strip()
    if not _looks_like_institution(line):
        return
    date_match = _DATE.search(line)
    date = date_match.group(0) if date_match else ""
    name = _DATE.sub("", line).strip(" -\t")
    _add(found, name, date)


def _looks_like_institution(text: str) -> bool:
    if not text or len(text) < 4 or len(text) > 160:
        return False
    if _NOISE.search(text):
        return False
    return bool(_INST_HINTS.search(text))


def _add(found: dict, name: str, date: str) -> None:
    name = re.sub(r"\s{2,}", " ", name).strip(" .-")
    key = name.lower()
    if not name:
        return
    if key not in found:
        found[key] = DiscoveredInstitution(name=name, relationship_start=date)
    elif date and not found[key].relationship_start:
        found[key].relationship_start = date
