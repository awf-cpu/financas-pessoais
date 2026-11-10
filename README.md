# 💰 Finanças Pessoais

Sistema **próprio, gratuito e auto-hospedado** para analisar suas contas e
cartões automaticamente. Pensado para o **Brasil / PT-BR**, roda no **seu VPS**
e abre tanto no **navegador do computador** quanto como **app no celular** (PWA).

> **Filosofia:** zero gasto novo. Usa só o que você já tem (VPS, e-mail,
> conta Hugging Face). Nenhuma API paga é obrigatória.

---

## O que ele faz

- **Importa** extratos e faturas em **OFX, CSV e PDF** (todo banco/cartão exporta de graça).
- **Ingestão automática por e-mail (IMAP/Gmail):** lê os extratos/faturas que o
  banco te manda por e-mail e processa os anexos sozinho.
- **Categoriza** as transações em português (mercado, transporte, streaming…) com
  um **motor de regras** (offline, grátis) + reforço opcional via **Hugging Face**.
- **Analisa:** saldo, entradas × saídas por mês, gastos por categoria, maiores despesas.
- **Dashboard PWA:** responsivo, instalável no celular (tela inicial) e no desktop.
- **Pluggy (Open Finance):** suporte **opcional** e desligado por padrão, caso um
  dia você queira conexão direta via o tier gratuito deles.

---

## Como a “automação de graça” funciona

Conexão bancária 100% automática no Brasil exige um agregador licenciado
(Pluggy/Belvo), que é **pago** (a partir de ~R$2.500/mês). Para ter automação
**sem custo**, este projeto usa dois caminhos:

| Caminho | Automático? | Custo | Como |
|---|---|---|---|
| **E-mail (IMAP)** | ✅ Sim, por cron | Grátis | Banco envia fatura/extrato por e-mail → o sistema lê os anexos |
| **Importar arquivo** | Semiautomático | Grátis | Você exporta OFX/CSV/PDF e envia pelo dashboard (1 clique) |
| **Pluggy** | ✅ Sim | Pago (opcional) | Open Finance; desligado por padrão |

Dica: configure seu banco/cartão para **enviar a fatura/extrato por e-mail** e
deixe o cron rodando — aí fica automático sem pagar nada.

### 🏦 Descobrir TODAS as suas contas — Registrato (Banco Central)

Não sabe em quais bancos você tem conta? O **[Registrato](https://www.bcb.gov.br/cidadaniafinanceira/registrato)**
do Banco Central mostra isso **de graça** (login **gov.br**):

1. Acesse o Registrato e faça login com gov.br.
2. Gere o **“Relatório de Relacionamentos com IFs (CCS)”** (PDF).
3. No dashboard, clique em **“Importar relatório CCS (PDF)”**.

O sistema lista **todas as instituições** onde seu CPF tem/teve relacionamento —
seu mapa para saber de onde coletar extratos. Obs.: o CCS mostra *onde* você tem
conta, **não** os saldos/extratos (esses você pega em cada banco, por OFX/e-mail).
Vale olhar também, no Registrato, o **Relatório de Chaves Pix** e o **SCR** (crédito).

> O login gov.br tem CAPTCHA e **não** é (nem deve ser) automatizado — por isso o
> fluxo é: você baixa o PDF e importa aqui com um clique.

---

## Rodando localmente (teste rápido)

```bash
cp .env.example .env            # edite APP_TOKEN (obrigatório)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# abra http://localhost:8000/?token=SEU_TOKEN
```

## Rodando no VPS (recomendado) com Docker

```bash
git clone <seu-repo> financas && cd financas
cp .env.example .env            # defina APP_TOKEN forte e, se quiser, IMAP/HF
docker compose up -d --build
```

O serviço `app` sobe na porta 8000 e o serviço `sync` sincroniza a cada 6h.
Coloque atrás de um proxy HTTPS (Caddy/Nginx/Traefik) com seu domínio.

### HTTPS rápido com Caddy (exemplo)

```
financas.seudominio.com {
    reverse_proxy localhost:8000
}
```

---

## Instalar como app no celular (PWA)

1. Abra `https://financas.seudominio.com/?token=SEU_TOKEN` no Chrome/Safari.
2. Menu do navegador → **“Adicionar à tela de início”**.
3. Pronto: abre em tela cheia, com ícone, igual a um app — sem loja, sem custo.

---

## Configuração (`.env`)

| Variável | Para quê | Obrigatório |
|---|---|---|
| `APP_TOKEN` | Senha de acesso ao dashboard | **Sim** |
| `DATABASE_URL` | SQLite (padrão) ou Postgres | Não |
| `IMAP_HOST`/`IMAP_USER`/`IMAP_PASSWORD` | Ingestão por e-mail (Gmail etc.) | Não |
| `HF_TOKEN` | Categorização via Hugging Face (grátis) | Não |
| `ANTHROPIC_API_KEY` | Categorização via Claude (pago) | Não |
| `PLUGGY_CLIENT_ID`/`SECRET` | Open Finance via Pluggy | Não |

### E-mail (Gmail): como pegar a senha de app
Com verificação em 2 etapas ativa, gere uma **senha de app** em
<https://myaccount.google.com/apppasswords> e use em `IMAP_PASSWORD`
(`IMAP_HOST=imap.gmail.com`). A leitura é **somente leitura** — nada é alterado,
movido ou apagado na sua caixa.

### Hugging Face (grátis)
Crie um token em <https://huggingface.co/settings/tokens> e coloque em `HF_TOKEN`.
Sem ele, a categorização usa só as regras (também funciona bem).

---

## Segurança e privacidade

- Seus dados ficam **no seu banco, no seu VPS**. Nada é enviado para terceiros,
  exceto se você **optar** por HF/Anthropic (só a descrição da transação) ou Pluggy.
- O arquivo `.env`, o banco (`*.db`) e quaisquer extratos estão no `.gitignore` —
  **nunca** vão para o Git.
- Sirva sempre atrás de **HTTPS** e use um `APP_TOKEN` forte.
- Faça backup da pasta `data/` (contém o banco).

---

## Estrutura

```
app/
  main.py          # FastAPI: API + dashboard PWA + auth por token
  config.py        # settings via .env
  models.py        # Connection / Account / Transaction
  categorize.py    # regras PT-BR + Hugging Face + (opcional) Anthropic
  analysis.py      # agregações para os gráficos
  ingest.py        # persistência + deduplicação
  sync.py          # orquestra e-mail + Pluggy
  providers/
    fileimport.py  # OFX / CSV / PDF
    email_imap.py  # ingestão por e-mail
    pluggy.py      # Open Finance (opcional)
  templates/ static/   # dashboard + PWA (manifest, service worker)
scripts/sync.py    # sincronização via cron
tests/             # testes de categorização e importação
```

## Testes

```bash
pytest -q
```

## Aviso

Ferramenta de uso pessoal para organizar finanças. Não é aconselhamento
financeiro. Confira sempre os números com o extrato oficial do seu banco.
