"""Configuracao da aplicacao, lida do ambiente (.env).

Nenhum segredo tem valor padrao utilizavel: JWT_SECRET_KEY e a senha do banco
sao obrigatorios e a aplicacao falha ao subir se estiverem ausentes. Isso e
deliberado — um segredo com valor padrao acaba indo para producao.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    # --- aplicacao ---
    app_name: str = "API de Predicao de Falhas em Motores Eletricos"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # --- banco ---
    postgres_user: str = "tcc"
    postgres_password: str                      # obrigatorio
    postgres_db: str = "tcc_motores"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # --- seguranca ---
    jwt_secret_key: str                         # obrigatorio
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False                 # true em producao (HTTPS)
    cookie_samesite: str = "lax"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    # --- upload de sinal bruto ---
    upload_dir: Path = PROJECT_ROOT / "backend" / "uploads"
    max_upload_mb: int = 50
    allowed_upload_suffixes: str = ".csv,.mat,.tdms,.npy,.wav"

    # --- modelo ---
    model_artifact: Path = PROJECT_ROOT / "ml" / "artifacts" / "model_v1.joblib"

    @field_validator("jwt_secret_key")
    @classmethod
    def _chave_forte(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY precisa de ao menos 32 caracteres")
        if v.startswith("gere-uma-chave"):
            raise ValueError("JWT_SECRET_KEY ainda esta com o valor de exemplo")
        return v

    @property
    def database_url(self) -> str:
        return (f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_suffixes(self) -> set[str]:
        return {s.strip().lower() for s in self.allowed_upload_suffixes.split(",") if s.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
