import streamlit as st

from src.config.settings import (
    BACEN_SERIES,
    DEFAULT_BACEN_END_DATE,
    DEFAULT_BACEN_START_DATE,
)
from src.config.universe import COMPANIES
from src.models.contracts import Filtros
from src.ui.dashboards import cvm_dashboard, macro_dashboard


def render() -> None:
    """Renderiza a view do BI Executivo permitindo alternar entre Dashboard Macro e CVM."""
    setores = tuple(sorted(list({info.setor_analitico for info in COMPANIES.values()})))

    filtros_padrao = Filtros(
        periodo=(DEFAULT_BACEN_START_DATE, DEFAULT_BACEN_END_DATE),
        tickers=tuple(COMPANIES.keys()),
        setores=setores,
        indicadores_bacen=tuple(BACEN_SERIES.keys()),
    )

    dash_opcao = st.sidebar.radio(
        "Selecione o Dashboard",
        options=["Dashboard 1 — Macro (BACEN)", "Dashboard 2 — Fundamentalista (CVM)"],
        index=0,
    )

    if dash_opcao == "Dashboard 1 — Macro (BACEN)":
        macro_dashboard.render(filtros_padrao)
    else:
        cvm_dashboard.render(filtros_padrao)