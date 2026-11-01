"""Gestão centralizada do estado de sessão (st.session_state).

Define a estrutura de navegação, os filtros globais e o estado do pipeline DataOps.
Sem leitura de dados ou I/O neste módulo.
"""

from __future__ import annotations

import gc
from typing import TYPE_CHECKING, Any, Dict, Optional
import streamlit as st

from src.config.settings import (
    BACEN_SERIES,
    DEFAULT_BACEN_END_DATE,
    DEFAULT_BACEN_START_DATE,
)
from src.config.universe import COMPANIES
from src.models.contracts import Filtros, PipelineParams

if TYPE_CHECKING:
    from src.etl.pipeline import PipelineOrchestrator


def get_default_filtros() -> Dict[str, Any]:
    """Retorna o dicionário de filtros globais com os valores padrão de config."""
    setores = sorted(list({info.setor_analitico for info in COMPANIES.values()}))
    return {
        "periodo": (DEFAULT_BACEN_START_DATE, DEFAULT_BACEN_END_DATE),
        "tickers": list(COMPANIES.keys()),
        "setores": setores,
        "indicadores_bacen": list(BACEN_SERIES.keys()),
    }


def init_state() -> None:
    """Inicializa as chaves do st.session_state caso não existam.
    
    Idempotente: preserva os valores existentes no estado de sessão.
    """
    if "modo" not in st.session_state:
        st.session_state["modo"] = None  # None | "dataops" | "bi"

    if "aba_ativa" not in st.session_state:
        st.session_state["aba_ativa"] = "d1_macro"

    if "filtros" not in st.session_state:
        st.session_state["filtros"] = get_default_filtros()

    if "dataops_params" not in st.session_state:
        st.session_state["dataops_params"] = None

    if "dataops_modo" not in st.session_state:
        st.session_state["dataops_modo"] = "sandbox"

    if "dataops_orchestrator" not in st.session_state:
        st.session_state["dataops_orchestrator"] = None

    if "dataops_logs" not in st.session_state:
        st.session_state["dataops_logs"] = []

    if "dataops_resultados" not in st.session_state:
        st.session_state["dataops_resultados"] = {}

    if "dataops_finalizado" not in st.session_state:
        st.session_state["dataops_finalizado"] = False


def ir_para(modo: str, aba: str = "d1_macro") -> None:
    """Altera o modo de navegação ativo ("dataops" ou "bi") e a aba inicial."""
    st.session_state["modo"] = modo
    st.session_state["aba_ativa"] = aba


def voltar_landing() -> None:
    """Retorna para a landing page redefinindo o modo para None."""
    st.session_state["modo"] = None


def reset_filtros() -> None:
    """Restaura os filtros globais para os valores padrão das configurações."""
    st.session_state["filtros"] = get_default_filtros()


def montar_filtros() -> Filtros:
    """Converte o estado atual de st.session_state["filtros"] em dataclass imutável Filtros."""
    if "filtros" not in st.session_state:
        st.session_state["filtros"] = get_default_filtros()

    f = st.session_state["filtros"]
    periodo_tuple = tuple(f.get("periodo", (DEFAULT_BACEN_START_DATE, DEFAULT_BACEN_END_DATE)))
    tickers_tuple = tuple(f.get("tickers", list(COMPANIES.keys())))
    setores_tuple = tuple(f.get("setores", []))
    indicadores_tuple = tuple(f.get("indicadores_bacen", list(BACEN_SERIES.keys())))

    return Filtros(
        periodo=periodo_tuple,
        tickers=tickers_tuple,
        setores=setores_tuple,
        indicadores_bacen=indicadores_tuple,
    )


def get_dataops_params() -> Optional[PipelineParams]:
    """Retorna os parâmetros atuais do DataOps."""
    return st.session_state.get("dataops_params")


def set_dataops_pipeline(params: PipelineParams, orchestrator: PipelineOrchestrator) -> None:
    """Define os parâmetros, modo e orquestrador do DataOps no estado."""
    st.session_state["dataops_params"] = params
    st.session_state["dataops_modo"] = params.modo
    st.session_state["dataops_orchestrator"] = orchestrator
    st.session_state["dataops_logs"] = []
    st.session_state["dataops_resultados"] = {}
    st.session_state["dataops_finalizado"] = False


def reset_dataops_pipeline() -> None:
    """Limpa o orquestrador, logs e parâmetros do DataOps ao alterar configurações."""
    st.session_state["dataops_params"] = None
    st.session_state["dataops_orchestrator"] = None
    st.session_state["dataops_logs"] = []
    st.session_state["dataops_resultados"] = {}
    st.session_state["dataops_finalizado"] = False


def add_dataops_log(log_event: Dict[str, Any], limit: int = 500) -> None:
    """Adiciona evento de log no estado mantendo limite máximo em memória."""
    if "dataops_logs" not in st.session_state:
        st.session_state["dataops_logs"] = []

    st.session_state["dataops_logs"].append(log_event)
    if len(st.session_state["dataops_logs"]) > limit:
        st.session_state["dataops_logs"] = st.session_state["dataops_logs"][-limit:]


def limpar_memoria_dataops() -> None:
    """Libera memória do pipeline mantendo resumo dos passos e logs para consulta."""
    orchestrator = st.session_state.get("dataops_orchestrator")
    if orchestrator is not None:
        st.session_state["dataops_resultados"] = orchestrator.estado()
        orchestrator.logger.clear_handlers()
        orchestrator.logger.clear_logs()

    st.session_state["dataops_orchestrator"] = None
    st.session_state["dataops_finalizado"] = True
    st.cache_data.clear()
    gc.collect()