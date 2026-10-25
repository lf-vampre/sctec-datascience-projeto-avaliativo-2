"""Utilitário para liberação explícita de memória e coleta de lixo."""

import gc
from typing import Any


def release(*objs: Any) -> None:
    """Deleta os objetos passados por parâmetro e força a execução do Garbage Collector."""
    for obj in objs:
        del obj
    gc.collect()