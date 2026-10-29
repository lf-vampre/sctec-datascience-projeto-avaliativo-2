"""Base do ETL: PipelineLogger, classes abstratas BaseExtractor/BaseCleaner e controle de execução."""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.config import settings
from src.models.contracts import PipelineParams, StepResult
from src.utils import paths
from src.utils.memory import release

# Configuração do logging padrão
logger_std = logging.getLogger("DataOpsPipeline")
if not logger_std.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger_std.addHandler(handler)
    logger_std.setLevel(logging.INFO)


class PipelineLogger:
    """Gerenciador de logs do pipeline com histórico em memória e notificações para UI."""

    def __init__(self) -> None:
        self.logs: List[Dict[str, Any]] = []
        self._handlers: List[Callable[[Dict[str, Any]], None]] = []

    def add_handler(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        """Adiciona um handler callback para ser notificado em cada evento emitido."""
        if fn not in self._handlers:
            self._handlers.append(fn)

    def emit(self, level: str, fonte: str, etapa: str, msg: str, **meta: Any) -> None:
        """Emite um log estruturado, armazena no histórico, aciona handlers e envia ao logging padrão."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "level": level.upper(),
            "fonte": fonte,
            "etapa": etapa,
            "message": msg,
            "metadata": meta,
        }
        self.logs.append(event)

        log_msg = f"[{fonte}] [{etapa}] {msg}"
        if level.upper() == "ERROR":
            logger_std.error(log_msg)
        elif level.upper() == "WARNING":
            logger_std.warning(log_msg)
        else:
            logger_std.info(log_msg)

        for handler_fn in self._handlers:
            try:
                handler_fn(event)
            except Exception:
                pass


def bronze_is_fresh(file_path: Path, ttl_days: int = settings.BRONZE_TTL_DAYS) -> bool:
    """Verifica se o arquivo Bronze existe e está dentro do TTL (mtime)."""
    if not file_path.exists():
        return False
    file_age_seconds = time.time() - file_path.stat().st_mtime
    ttl_seconds = ttl_days * 86400
    return file_age_seconds < ttl_seconds


def get_layer_path(params: PipelineParams, layer: str) -> Path:
    """Roteia o caminho da camada de dados respeitando o modo (sandbox vs producao)."""
    base = paths.SANDBOX_DIR if params.is_sandbox else paths.DATA_DIR
    layer_dir = base / layer
    layer_dir.mkdir(parents=True, exist_ok=True)
    return layer_dir


class BaseExtractor(ABC):
    """Classe base para extratores de dados da camada Bronze."""

    def __init__(self, logger: PipelineLogger, storage_writer: Optional[Any] = None) -> None:
        self.logger = logger
        self.storage_writer = storage_writer

    @abstractmethod
    def extract(self, params: PipelineParams) -> StepResult:
        """Implementação específica de extração para a fonte."""
        pass

    def run_bronze(self, params: PipelineParams) -> StepResult:
        """Executa a etapa Bronze monitorando tempo, exceções e liberando memória."""
        start_time = time.time()
        step_id = f"extract_{self.__class__.__name__}"
        self.logger.emit("INFO", self.__class__.__name__, "START", f"Iniciando extração ({params.modo})")
        try:
            result = self.extract(params)
            result.duration_s = time.time() - start_time
            self.logger.emit(
                "INFO" if result.ok else "ERROR",
                self.__class__.__name__,
                "END",
                f"Concluído com ok={result.ok} em {result.duration_s:.2f}s",
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            err_msg = str(e)
            self.logger.emit("ERROR", self.__class__.__name__, "FAILURE", f"Falha na extração: {err_msg}")
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                duration_s=duration,
                error=err_msg,
            )
        finally:
            release()


class BaseCleaner(ABC):
    """Classe base para higienizadores e transformadores da camada Prata."""

    def __init__(self, logger: PipelineLogger, storage_writer: Optional[Any] = None) -> None:
        self.logger = logger
        self.storage_writer = storage_writer

    @abstractmethod
    def clean(self, params: PipelineParams) -> StepResult:
        """Implementação específica de limpeza para a fonte."""
        pass

    def run_silver(self, params: PipelineParams) -> StepResult:
        """Executa a etapa Prata monitorando tempo, exceções e liberando memória."""
        start_time = time.time()
        step_id = f"clean_{self.__class__.__name__}"
        self.logger.emit("INFO", self.__class__.__name__, "START", f"Iniciando limpeza ({params.modo})")
        try:
            result = self.clean(params)
            result.duration_s = time.time() - start_time
            self.logger.emit(
                "INFO" if result.ok else "ERROR",
                self.__class__.__name__,
                "END",
                f"Concluído com ok={result.ok} em {result.duration_s:.2f}s",
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            err_msg = str(e)
            self.logger.emit("ERROR", self.__class__.__name__, "FAILURE", f"Falha na limpeza: {err_msg}")
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                duration_s=duration,
                error=err_msg,
            )
        finally:
            release()


# ------------------------------------------------------------------------------
# Controle de Execução Global (Desativado / Simples)
# ------------------------------------------------------------------------------
def seconds_until_allowed(modo: str) -> float:
    """Retorna sempre 0 para desativar a trava temporal."""
    return 0.0


def try_acquire(modo: str) -> bool:
    """Retorna sempre True para desativar o bloqueio de concorrência global."""
    return True


def release_lock() -> None:
    """Sem efeito por causa da remoção do lock global."""
    pass