"""
Gestão centralizada do estado de sessão (st.session_state).
Define a estrutura de navegação e os filtros globais da aplicação.
Sem leitura de dados ou I/O neste módulo.
"""

from typing import Any, Dict
import streamlit as st

from src.config.settings import (
    BACEN_SERIES,
    DEFAULT_CVM_END_YEAR,
    DEFAULT_CVM_START_YEAR,
)
from src.config.universe import COMPANIES


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