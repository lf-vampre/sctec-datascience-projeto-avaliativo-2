"""Gestão centralizada do estado de sessão (st.session_state).

Define a estrutura de navegação, os filtros globais e o estado do pipeline DataOps.
Sem leitura de dados ou I/O neste módulo.
"""

import gc
from typing import Any, Dict, List, Optional
import streamlit as st

from src.config.settings import (
    BACEN_SERIES,
    DEFAULT_CVM_END_YEAR,
    DEFAULT_CVM_START_YEAR,
)
from src.config.universe import COMPANIES
from src.etl.pipeline import PipelineOrchestrator
from src.models.contracts import PipelineParams


def get_default_filtros() -> Dict[str, Any]:
    """Retorna o dicionário de filtros globais com os valores padrão de config."""
    setores = sorted(list({info.setor_analitico for info in COMPANIES.values()}))
    return {
        "periodo": (DEFAULT_CVM_START_YEAR, DEFAULT_CVM_END_YEAR),
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


def get_dataops_params() -> Optional[PipelineParams]:
    """Retorna os parâmetros atuais do DataOps."""
    return st.session_state.get("dataops_params")


def set_dataops_pipeline(params: PipelineParams, orchestrator: PipelineOrchestrator) -> None:
    """Define os parâmetros, modo e orquestrador do DataOps no estado."""
    st.session_state["dataops_params"] = params
    st.session_state["dataops_modo"] = params.modo
    st.session_state["dataops_orchestrator"] = orchestrator
    st.session_state["dataops_logs"] = []


def reset_dataops_pipeline() -> None:
    """Limpa o orquestrador, logs e parâmetros do DataOps ao alterar configurações."""
    st.session_state["dataops_params"] = None
    st.session_state["dataops_orchestrator"] = None
    st.session_state["dataops_logs"] = []


def add_dataops_log(log_event: Dict[str, Any], limit: int = 500) -> None:
    """Adiciona evento de log no estado mantendo limite máximo em memória."""
    if "dataops_logs" not in st.session_state:
        st.session_state["dataops_logs"] = []

    st.session_state["dataops_logs"].append(log_event)
    if len(st.session_state["dataops_logs"]) > limit:
        st.session_state["dataops_logs"] = st.session_state["dataops_logs"][-limit:]


def limpar_memoria_dataops() -> None:
    """Força coleta de lixo, limpa cache de dados e reseta estado do orquestrador."""
    reset_dataops_pipeline()
    st.cache_data.clear()
    gc.collect()