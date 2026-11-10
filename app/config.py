"""Configuração central lida de variáveis de ambiente / arquivo .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Banco
    database_url: str = "sqlite:///data/financas.db"

    # Segurança do dashboard
    app_token: str = "troque-me-por-um-token-forte"

    # Pluggy (Open Finance) — OPCIONAL e desligado por padrão (evita custo).
    pluggy_client_id: str = ""
    pluggy_client_secret: str = ""
    pluggy_base_url: str = "https://api.pluggy.ai"

    # Categorização por IA — tudo opcional. Sem nada configurado, usa só regras.
    # 1) Hugging Face Inference API (GRÁTIS, tier gratuito) — backend preferido.
    hf_token: str = ""
    hf_model: str = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
    hf_base_url: str = "https://api-inference.huggingface.co"
    # 2) Anthropic (opcional, PAGO) — só se você quiser e tiver chave.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"

    # Ingestão automática por e-mail (IMAP) — ex.: Gmail. GRÁTIS.
    imap_host: str = ""           # ex.: imap.gmail.com
    imap_port: int = 993
    imap_user: str = ""           # seu e-mail
    imap_password: str = ""       # senha de app (não a senha normal)
    imap_folder: str = "INBOX"
    imap_search_days: int = 30    # janela de busca de e-mails recentes

    # Localização
    default_currency: str = "BRL"
    timezone: str = "America/Sao_Paulo"

    @property
    def pluggy_enabled(self) -> bool:
        return bool(self.pluggy_client_id and self.pluggy_client_secret)

    @property
    def hf_enabled(self) -> bool:
        return bool(self.hf_token)

    @property
    def anthropic_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def imap_enabled(self) -> bool:
        return bool(self.imap_host and self.imap_user and self.imap_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
