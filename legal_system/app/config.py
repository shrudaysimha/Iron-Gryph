"""Configuration settings for Legal & Investigation Document Management System."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "IronGryph Legal & Evidence Vault"
    app_version: str = "1.0.0"
    secret_key: str = "legal-evidence-vault-secure-jwt-key-2026"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    database_url: str = f"sqlite:///{BASE_DIR}/legal_vault.db"
    upload_dir: str = str(UPLOAD_DIR)

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
