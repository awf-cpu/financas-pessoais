# personal-finance-hub

[![CI](https://github.com/awf-cpu/financas-pessoais/actions/workflows/ci.yml/badge.svg)](https://github.com/awf-cpu/financas-pessoais/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A **self-hosted personal finance analyzer** built for Brazil: it imports bank statements and card bills, categorizes every transaction in Portuguese and shows the result in a mobile-friendly dashboard (installable PWA). No paid API is required; the free path is the default. (Portuguese README: [README.pt-BR.md](README.pt-BR.md).)

## What it shows

- **Ingestion** from OFX, CSV and PDF files, plus an optional read-only IMAP reader that picks up statements your bank emails you.
- **Categorization** with an offline PT-BR rule engine; optional second opinion from Hugging Face (free tier) or Claude. Only the transaction description leaves the machine, and only if you opt in.
- **Analysis**: balance, income vs. spending per month, spending by category, largest expenses.
- **Provider abstraction** (`app/providers/`): file import, IMAP, Pluggy (Open Finance, off by default) and a parser for the Central Bank "Registrato" report, all behind one interface.
- **Security basics**: token-protected API (constant-time comparison, example token refused, HttpOnly cookie), 10 MB upload cap, non-root Docker image, healthcheck.

## Stack

FastAPI, SQLAlchemy (SQLite by default, Postgres supported), Pydantic Settings, pdfplumber, ofxparse, vanilla JS PWA with a service worker, Docker Compose.

## Run it

```bash
cp .env.example .env            # set APP_TOKEN to a strong random value
pip install -r requirements.txt
uvicorn app.main:app            # open http://localhost:8000/?token=YOUR_TOKEN
pytest -q                       # 17 tests, offline
```

Or `docker compose up -d`. Serve it behind HTTPS in production.

## Design notes

- Free-first: every paid integration is optional and disabled unless configured.
- Parsers are tolerant and covered by tests (`tests/`); the Registrato PDF parser is heuristic by nature because the layout can change.
- No real financial data is in this repository. The sample inputs are synthetic.

MIT licensed. Built by [André Feix](https://github.com/awf-cpu).
