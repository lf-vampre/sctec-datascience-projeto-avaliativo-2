"""Gerenciamento de conexão resiliente com o banco PostgreSQL (Neon)."""

import os
import tomllib
from typing import Any, Dict, Optional
from sqlalchemy import Engine, create_engine, text
from src.utils.paths import ROOT_DIR


def _load_db_credentials() -> Dict[str, Any]:
    """Carrega credenciais do .streamlit/secrets.toml ou variáveis de ambiente sem importar streamlit."""
    secrets_path = ROOT_DIR / ".streamlit" / "secrets.toml"
    
    if secrets_path.exists():
        try:
            with open(secrets_path, "rb") as f:
                secrets = tomllib.load(f)
                if "connections" in secrets and "postgresql" in secrets["connections"]:
                    return dict(secrets["connections"]["postgresql"])
        except Exception:
            pass

    return {
        "dialect": os.getenv("POSTGRES_DIALECT", "postgresql"),
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "database": os.getenv("POSTGRES_DB"),
        "username": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "sslmode": os.getenv("POSTGRES_SSLMODE", "require"),
    }


def get_engine() -> Optional[Engine]:
    """Cria e retorna uma Engine SQLAlchemy configurada com pool_pre_ping e timeout curto."""
    creds = _load_db_credentials()
    
    host = creds.get("host")
    user = creds.get("username")
    password = creds.get("password")
    database = creds.get("database")
    port = creds.get("port", 5432)
    sslmode = creds.get("sslmode", "require")
    dialect = creds.get("dialect", "postgresql")

    if not all([host, user, password, database]):
        return None

    url = f"{dialect}://{user}:{password}@{host}:{port}/{database}?sslmode={sslmode}"
    
    try:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
        return engine
    except Exception:
        return None


def is_available() -> bool:
    """Testa a disponibilidade da conexão com o banco de dados. Retorna bool e nunca lança exceção."""
    try:
        engine = get_engine()
        if engine is None:
            return False
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False