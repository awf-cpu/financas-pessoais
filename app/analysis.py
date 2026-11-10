"""Agregações para o dashboard (consultas de leitura sobre as transações)."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Account, Transaction


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def overview(db: Session, months: int = 6) -> dict:
    """Resumo geral + séries para os gráficos dos últimos `months` meses."""
    start = _start_of_month(date.today(), months - 1)

    rows = db.scalars(
        select(Transaction).where(Transaction.date >= start).order_by(Transaction.date)
    ).all()

    total_in = sum(t.amount for t in rows if t.amount > 0)
    total_out = sum(-t.amount for t in rows if t.amount < 0)

    # Gastos por categoria (apenas saídas)
    by_category: dict[str, float] = {}
    for t in rows:
        if t.amount < 0:
            by_category[t.category] = by_category.get(t.category, 0.0) + (-t.amount)
    by_category_sorted = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)

    # Evolução mensal (entradas x saídas)
    months_list = _month_range(start, date.today())
    monthly = {m: {"in": 0.0, "out": 0.0} for m in months_list}
    for t in rows:
        mk = _month_key(t.date)
        if mk in monthly:
            if t.amount > 0:
                monthly[mk]["in"] += t.amount
            else:
                monthly[mk]["out"] += -t.amount

    # Maiores despesas do período
    top_expenses = sorted(
        ({"date": t.date.isoformat(), "description": t.description,
          "amount": t.amount, "category": t.category}
         for t in rows if t.amount < 0),
        key=lambda x: x["amount"],
    )[:10]

    # Saldo somado das contas
    balance = db.scalar(select(func.coalesce(func.sum(Account.balance), 0.0))) or 0.0

    return {
        "period": {"start": start.isoformat(), "end": date.today().isoformat(), "months": months},
        "totals": {
            "income": round(total_in, 2),
            "expense": round(total_out, 2),
            "net": round(total_in - total_out, 2),
            "balance": round(float(balance), 2),
            "transactions": len(rows),
        },
        "by_category": [{"category": c, "total": round(v, 2)} for c, v in by_category_sorted],
        "monthly": [
            {"month": m, "income": round(v["in"], 2), "expense": round(v["out"], 2)}
            for m, v in monthly.items()
        ],
        "top_expenses": top_expenses,
    }


def list_transactions(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    category: str | None = None,
    search: str | None = None,
) -> list[dict]:
    stmt = select(Transaction).order_by(Transaction.date.desc(), Transaction.id.desc())
    if category:
        stmt = stmt.where(Transaction.category == category)
    if search:
        stmt = stmt.where(Transaction.description.ilike(f"%{search}%"))
    stmt = stmt.limit(limit).offset(offset)
    return [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "description": t.description,
            "amount": t.amount,
            "category": t.category,
            "category_source": t.category_source,
        }
        for t in db.scalars(stmt).all()
    ]


def _start_of_month(ref: date, months_back: int) -> date:
    y, m = ref.year, ref.month - months_back
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _month_range(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out
