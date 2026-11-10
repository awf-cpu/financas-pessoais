"""Categorização de transações para o contexto brasileiro.

Estratégia em camadas:
  1. Motor de REGRAS (regex PT-BR) — rápido, offline, sem custo. Resolve a
     maioria das descrições de bancos/cartões BR ("PIX", "IFOOD", "UBER"...).
  2. Fallback LLM (Anthropic) — opcional, só é chamado para o que as regras
     não resolveram, se ANTHROPIC_API_KEY estiver definido.

Categorias propositalmente enxutas e em português.
"""
from __future__ import annotations

import re

CATEGORIES = [
    "Alimentação",
    "Mercado",
    "Transporte",
    "Moradia",
    "Contas & Serviços",
    "Saúde",
    "Educação",
    "Lazer & Streaming",
    "Compras",
    "Viagem",
    "Investimentos",
    "Transferências",
    "Receitas",
    "Tarifas & Juros",
    "Impostos",
    "Não categorizado",
]

# Cada regra: (categoria, lista de padrões regex, case-insensitive).
# A ordem importa — a primeira que casar vence.
_RULES: list[tuple[str, list[str]]] = [
    ("Receitas", [r"\bsal[aá]rio\b", r"\bprovento", r"\bremunera", r"rendimento", r"\bcredito de", r"\brestitui"]),
    ("Investimentos", [r"\btesouro\b", r"\bcdb\b", r"\blci\b", r"\blca\b", r"\bfundo\b", r"aplica[cç][aã]o", r"resgate", r"corretora", r"\bxp\b", r"nuinvest", r"rico\b", r"clear\b", r"a[cç][aã]o|a[cç][oõ]es| bolsa"]),
    ("Tarifas & Juros", [r"tarifa", r"\bjuros\b", r"\biof\b", r"anuidade", r"manuten[cç][aã]o de conta", r"encargos", r"multa"]),
    ("Impostos", [r"\bdarf\b", r"\bdas\b", r"\bgps\b", r"\bgnre\b", r"imposto", r"\birpf\b", r"\biptu\b", r"\bipva\b", r"licenciamento"]),
    ("Mercado", [r"supermercad", r"mercado\b", r"atacad", r"hortifr", r"assa[ií]", r"carrefour", r"p[aã]o de a[cç]ucar", r"big\b", r"extra\b", r"sacol[aã]o", r"\bdia\b", r"makro", r"sam'?s club"]),
    ("Alimentação", [r"ifood", r"rappi", r"ubereats|uber eats", r"restaurante", r"lanchonete", r"padaria", r"\bcafe\b|cafeteria", r"\bbar\b", r"pizzar", r"hamburgu", r"mcdonald|bk\b|burger king|subway|habib", r"a[cç]a[ií]|doceria|sorveter"]),
    ("Transporte", [r"\buber\b", r"\b99\b|99app|99 ?pop", r"cabify", r"\btaxi\b", r"posto\b|combust[ií]vel|gasolina|shell|ipiranga|petrobr|ale\b", r"estacionamento", r"\bped[aá]gio|sem parar|conectcar|veloe", r"metr[oô]|\bcptm\b|bilhete [uú]nico|\bbus\b|rodovi[aá]ri", r"localiza|movida|unidas|loca[cç][aã]o de ve[ií]culo"]),
    ("Moradia", [r"alugu[eé]l", r"condom[ií]nio", r"imobili[aá]ria", r"\biptu\b", r"financiamento imob"]),
    ("Contas & Serviços", [r"\benel\b|\bcpfl\b|\blight\b|\bcemig\b|\bcelesc\b|\bcoelba\b|energia el[eé]tr", r"\bsabesp\b|\bcedae\b|\bcopasa\b|\bsanepar\b|\b[aá]gua e esgoto", r"\bvivo\b|\bclaro\b|\btim\b|\boi\b|\bnextel\b|internet|telefon|banda larga", r"\bgas\b|comgas|ultragaz", r"assinatura", r"correios"]),
    ("Saúde", [r"farm[aá]cia|drogaria|drogasil|pacheco|raia|pague menos|ultrafarma", r"\bhospital\b|cl[ií]nica|laborat[oó]rio|\bexame\b|consulta m[eé]dica", r"unimed|amil|bradesco sa[uú]de|sulam[eé]rica|hapvida|notredame|plano de sa[uú]de", r"dentista|odonto|psic[oó]log|fisioterap"]),
    ("Educação", [r"faculdade|universidad|\bcurso\b|escola|col[eé]gio|mensalidade escolar", r"udemy|alura|coursera|hotmart|\bebook|livraria", r"\bidioma|ingl[eê]s|wizard|cultura inglesa|cna\b"]),
    ("Lazer & Streaming", [r"netflix|spotify|disney|hbo|max\b|prime video|amazon prime|youtube premium|deezer|globoplay|paramount|apple tv|apple\.com/bill", r"cinema|cinemark|teatro|show\b|ingresso|ticket", r"\bgame|steam|playstation|xbox|nintendo|riot", r"academia|smart ?fit|gympass|crossfit"]),
    ("Compras", [r"amazon|mercadolivre|mercado livre|magazine|magalu|americanas|shopee|aliexpress|shein|casas bahia|ponto frio", r"loja|shopping|renner|riachuelo|c&a|zara|centauro|netshoes|nike|adidas", r"\bapple\b|samsung|kabum|pichau|terabyte"]),
    ("Viagem", [r"\bgol\b|\blatam\b|\bazul\b|airlines|avia[cç][aã]o|passagem a[eé]rea", r"hotel|pousada|airbnb|booking|hostel|resort|hospedagem", r"\b123milhas|decolar|maxmilhas|cvc\b"]),
    ("Transferências", [r"\bpix\b", r"\bted\b", r"\bdoc\b", r"transfer[eê]ncia", r"\bp2p\b", r"enviado para|recebido de"]),
]

_COMPILED: list[tuple[str, list[re.Pattern[str]]]] = [
    (cat, [re.compile(p, re.IGNORECASE) for p in pats]) for cat, pats in _RULES
]


def categorize_by_rules(description: str, amount: float = 0.0) -> str | None:
    """Retorna a categoria pela primeira regra que casar, ou None."""
    text = description or ""
    for category, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                # Refinamento: PIX/TED de entrada costuma ser receita.
                if category == "Transferências" and amount > 0:
                    return "Receitas"
                return category
    return None


def categorize(description: str, amount: float = 0.0) -> tuple[str, str]:
    """Categoriza uma transação.

    Ordem (para por na primeira que resolver):
      1. REGRAS PT-BR  -> origem "rules"   (grátis, offline)
      2. Hugging Face  -> origem "hf"      (grátis, se HF_TOKEN definido)
      3. Anthropic     -> origem "llm"     (pago, só se habilitado)
      4. padrão        -> origem "default"
    """
    cat = categorize_by_rules(description, amount)
    if cat:
        return cat, "rules"

    cat = _categorize_by_hf(description)
    if cat:
        return cat, "hf"

    cat = _categorize_by_anthropic(description, amount)
    if cat:
        return cat, "llm"

    return "Não categorizado", "default"


_CANDIDATE_LABELS = [c for c in CATEGORIES if c != "Não categorizado"]


def _categorize_by_hf(description: str) -> str | None:
    """Zero-shot classification via Hugging Face Inference API (grátis).

    Usa um modelo multilíngue (NLI) que entende português. Silencioso em falha.
    """
    from .config import get_settings

    s = get_settings()
    if not s.hf_enabled or not (description or "").strip():
        return None
    try:
        import httpx

        url = f"{s.hf_base_url.rstrip('/')}/models/{s.hf_model}"
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {s.hf_token}"},
            json={
                "inputs": description,
                "parameters": {
                    "candidate_labels": _CANDIDATE_LABELS,
                    "hypothesis_template": "Esta transação é da categoria {}.",
                },
            },
            timeout=20.0,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        labels = data.get("labels") or []
        scores = data.get("scores") or []
        if labels and scores and scores[0] >= 0.45:  # limiar de confiança
            return labels[0]
    except Exception:
        return None
    return None


def _categorize_by_anthropic(description: str, amount: float) -> str | None:
    """Fallback opcional via Anthropic (PAGO). Silencioso em qualquer falha."""
    from .config import get_settings

    s = get_settings()
    if not s.anthropic_enabled:
        return None
    try:
        import anthropic  # import tardio: dependência só é exigida se usada

        client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        cats = ", ".join(_CANDIDATE_LABELS)
        sign = "saída/gasto" if amount < 0 else "entrada/receita"
        msg = client.messages.create(
            model=s.anthropic_model,
            max_tokens=16,
            system=(
                "Você categoriza transações bancárias brasileiras. "
                f"Responda APENAS com uma destas categorias, nada mais: {cats}."
            ),
            messages=[{
                "role": "user",
                "content": f'Transação ({sign}): "{description}". Categoria:',
            }],
        )
        text = "".join(
            b.text for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
        for c in CATEGORIES:
            if c.lower() in text.lower():
                return c
    except Exception:
        return None
    return None
