"""Contratos de dados (dataclasses) trocados entre ETL, Warehouse e UI."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PipelineParams:
    """Parâmetros de execução do pipeline DataOps."""

    tickers: List[str]
    bacen_periodo: Tuple[str, str]  # ("YYYY-MM-DD", "YYYY-MM-DD")
    b3_periodo: Tuple[str, str]     # ("YYYY-MM-DD", "YYYY-MM-DD")
    cvm_anos: List[int]            # Ex: [2021, 2022, 2023]
    is_sandbox: bool = True


@dataclass
class StepResult:
    """Resultado serializável da execução de uma etapa do pipeline."""

    step_id: str
    ok: bool
    rows: int = 0
    paths: List[str] = field(default_factory=list)
    duration_s: float = 0.0
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(frozen=True)
class Filtros:
    """Filtros globais e locais aplicados na interface BI Executivo."""

    periodo: Tuple[str, str]
    tickers: Tuple[str, ...]
    setores: Tuple[str, ...]
    indicadores_bacen: Tuple[str, ...]