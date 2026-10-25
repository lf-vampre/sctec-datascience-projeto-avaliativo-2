"""Utilitário de caminhos do projeto utilizando pathlib."""

from pathlib import Path

# Raiz do projeto (duas pastas acima de src/utils/paths.py)
ROOT_DIR: Path = Path(__file__).resolve().parents[2]

# Diretórios de dados
DATA_DIR: Path = ROOT_DIR / "data"
BRONZE_DIR: Path = DATA_DIR / "bronze"
SILVER_DIR: Path = DATA_DIR / "silver"
GOLD_DIR: Path = DATA_DIR / "gold"
SANDBOX_DIR: Path = DATA_DIR / "_sandbox"


def ensure_directories() -> None:
    """Garante que todos os diretórios de dados existam."""
    for path in [BRONZE_DIR, SILVER_DIR, GOLD_DIR, SANDBOX_DIR]:
        path.mkdir(parents=True, exist_ok=True)