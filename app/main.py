"""Aplicação FastAPI: API JSON + dashboard PWA.

Segurança simples (adequada a uso pessoal): todas as rotas, exceto os assets
estáticos da PWA, exigem o token do .env, via header `X-App-Token`, query
`?token=` ou cookie `app_token` (gravado ao entrar com ?token=).
Em produção, sirva sempre atrás de HTTPS.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import analysis
from .config import get_settings
from .database import get_db, init_db
from .ingest import ingest_accounts
from .providers import fileimport
from .sync import run_sync

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Finanças Pessoais", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Rotas públicas (necessárias para a PWA instalar/funcionar sem token).
_PUBLIC_PATHS = {"/manifest.webmanifest", "/sw.js", "/login", "/health", "/favicon.ico"}


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --------------------------------------------------------------------------
# Autenticação por token
# --------------------------------------------------------------------------
def _token_ok(request: Request) -> bool:
    expected = get_settings().app_token
    provided = (
        request.headers.get("X-App-Token")
        or request.query_params.get("token")
        or request.cookies.get("app_token")
    )
    return bool(provided) and provided == expected


def require_token(request: Request) -> None:
    if not _token_ok(request):
        raise HTTPException(status_code=401, detail="Token inválido ou ausente.")


@app.middleware("http")
async def _auth_guard(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith("/static/"):
        return await call_next(request)
    if not _token_ok(request):
        # Navegador -> página de login; API -> 401 JSON.
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(url="/login")
        return JSONResponse({"detail": "Não autorizado"}, status_code=401)
    response = await call_next(request)
    # Se entrou com ?token=, grava cookie para as próximas visitas.
    token = request.query_params.get("token")
    if token and token == get_settings().app_token:
        response.set_cookie(
            "app_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 90
        )
    return response


# --------------------------------------------------------------------------
# Páginas (HTML / PWA)
# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "pluggy": s.pluggy_enabled,
        "huggingface": s.hf_enabled,
        "email_imap": s.imap_enabled,
    }


# PWA: manifest e service worker na raiz (escopo correto).
@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(BASE_DIR / "static" / "manifest.webmanifest",
                        media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(BASE_DIR / "static" / "sw.js", media_type="application/javascript")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(BASE_DIR / "static" / "icon.svg", media_type="image/svg+xml")


# --------------------------------------------------------------------------
# API JSON
# --------------------------------------------------------------------------
@app.get("/api/overview", dependencies=[Depends(require_token)])
def api_overview(months: int = 6, db: Session = Depends(get_db)):
    return analysis.overview(db, months=months)


@app.get("/api/transactions", dependencies=[Depends(require_token)])
def api_transactions(
    limit: int = 100,
    offset: int = 0,
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    return analysis.list_transactions(
        db, limit=limit, offset=offset, category=category, search=search
    )


@app.post("/api/upload", dependencies=[Depends(require_token)])
async def api_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        raw = fileimport.import_file(file.filename or "arquivo", content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = ingest_accounts(
        db, [raw], provider="fileimport", institution=file.filename or ""
    )
    return {
        "arquivo": file.filename,
        "conta": raw.name,
        "importadas": result.inserted,
        "duplicadas_ignoradas": result.skipped,
    }


@app.post("/api/sync", dependencies=[Depends(require_token)])
def api_sync(db: Session = Depends(get_db)):
    report = run_sync(db)
    return {
        "fontes": report.sources,
        "importadas": report.inserted,
        "duplicadas_ignoradas": report.skipped,
        "contas": report.accounts,
        "erros": report.errors,
    }


# --- Registrato (Banco Central): mapa de todas as instituições do CPF ---
@app.get("/api/institutions", dependencies=[Depends(require_token)])
def api_institutions(db: Session = Depends(get_db)):
    from sqlalchemy import select

    from .models import Institution

    rows = db.scalars(select(Institution).order_by(Institution.name)).all()
    return {
        "registrato_url": "https://www.bcb.gov.br/cidadaniafinanceira/registrato",
        "instituicoes": [
            {
                "id": i.id,
                "nome": i.name,
                "inicio_relacionamento": i.relationship_start,
                "status": i.status,
            }
            for i in rows
        ],
    }


@app.post("/api/registrato", dependencies=[Depends(require_token)])
async def api_registrato(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa o PDF do relatório CCS do Registrato e cadastra as instituições."""
    from sqlalchemy import select

    from .models import Institution
    from .providers.registrato import parse_ccs_pdf

    content = await file.read()
    try:
        discovered = parse_ccs_pdf(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha ao ler o PDF do CCS: {e}")

    novas = 0
    for d in discovered:
        exists = db.scalars(select(Institution).where(Institution.name == d.name)).first()
        if exists:
            continue
        db.add(Institution(name=d.name, relationship_start=d.relationship_start))
        novas += 1
    db.commit()
    return {
        "encontradas": len(discovered),
        "novas": novas,
        "instituicoes": [d.name for d in discovered],
    }
