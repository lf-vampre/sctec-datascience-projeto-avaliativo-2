import streamlit as st

from src.config.settings import (
    BACEN_SERIES,
    DEFAULT_BACEN_END_DATE,
    DEFAULT_BACEN_START_DATE,
)
from src.config.universe import COMPANIES
from src.models.contracts import Filtros
from src.ui.dashboards import macro_dashboard


def render() -> None:
    """Renderiza a view do BI Executivo chamando o Dashboard Macro com filtros padrão."""
    setores = tuple(sorted(list({info.setor_analitico for info in COMPANIES.values()})))

    filtros_padrao = Filtros(
        periodo=(DEFAULT_BACEN_START_DATE, DEFAULT_BACEN_END_DATE),
        tickers=tuple(COMPANIES.keys()),
        setores=setores,
        indicadores_bacen=tuple(BACEN_SERIES.keys()),
    )

    macro_dashboard.render(filtros_padrao)