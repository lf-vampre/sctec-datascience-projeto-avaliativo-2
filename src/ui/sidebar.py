"""Componente de sidebar global para navegação e filtros cruzados do BI Executivo."""

from datetime import date, datetime
from typing import List, Tuple

import pandas as pd
import streamlit as st

from src.config.settings import (
    BACEN_SERIES,
    DEFAULT_BACEN_END_DATE,
    DEFAULT_BACEN_START_DATE,
)
from src.config.universe import COMPANIES
from src.models.contracts import Filtros
from src.ui.data_loader import DadosIndisponiveis, load_dim
from src.ui.state import get_default_filtros, montar_filtros, reset_filtros


def _obter_dados_empresas() -> pd.DataFrame:
    """Carrega dados das empresas da Ouro com fallback para a configuração estática."""
    try:
        carga = load_dim("dim_empresa")
        df = carga.dados
        if df is not None and not df.empty:
            return df
    except (DadosIndisponiveis, Exception):
        pass

    registros = []
    for ticker, info in COMPANIES.items():
        registros.append(
            {
                "ticker": ticker,
                "setor_analitico": info.setor_analitico,
                "denom_cia": info.denom_cia,
                "tem_cvm": info.tem_cvm,
                "tem_b3": info.tem_b3,
            }
        )
    return pd.DataFrame(registros)


def _parse_date(valor: str) -> date:
    """Converte string YYYY-MM-DD para objeto date."""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date(2019, 1, 1)


def render() -> Filtros:
    """Renderiza os filtros globais na sidebar e devolve o contrato Filtros imutável."""
    if "filtros" not in st.session_state:
        st.session_state["filtros"] = get_default_filtros()

    f_state = st.session_state["filtros"]

    df_emp = _obter_dados_empresas()
    todos_setores = sorted(list(df_emp["setor_analitico"].dropna().unique()))

    setores_salvos = [s for s in f_state.get("setores", []) if s in todos_setores]
    if not setores_salvos and "setores" not in f_state:
        setores_salvos = todos_setores

    setores_selecionados = st.sidebar.multiselect(
        "Setores",
        options=todos_setores,
        default=setores_salvos,
        help="Filtra a lista de empresas pelos setores selecionados.",
    )

    if setores_selecionados:
        df_filtrado = df_emp[df_emp["setor_analitico"].isin(setores_selecionados)]
    else:
        df_filtrado = df_emp

    tickers_validos = sorted(list(df_filtrado["ticker"].dropna().unique()))

    tickers_salvos = [t for t in f_state.get("tickers", []) if t in tickers_validos]
    if not tickers_salvos and not f_state.get("setores"):
        tickers_salvos = tickers_validos

    tickers_selecionados = st.sidebar.multiselect(
        "Ativos / Empresas",
        options=tickers_validos,
        default=tickers_salvos,
        help="Seleciona as empresas/tickers considerados nas análises.",
    )

    p_ini_str, p_fim_str = f_state.get(
        "periodo", (DEFAULT_BACEN_START_DATE, DEFAULT_BACEN_END_DATE)
    )
    p_ini_date = _parse_date(p_ini_str)
    p_fim_date = _parse_date(p_fim_str)

    periodo_input = st.sidebar.date_input(
        "Período de Análise",
        value=(p_ini_date, p_fim_date),
        help="Define a janela temporal global para consulta de cotações, demonstrativos e dados macro.",
    )

    if isinstance(periodo_input, (tuple, list)) and len(periodo_input) == 2:
        d_ini, d_fim = periodo_input[0], periodo_input[1]
    elif isinstance(periodo_input, (tuple, list)) and len(periodo_input) == 1:
        d_ini, d_fim = periodo_input[0], periodo_input[0]
    else:
        d_ini, d_fim = p_ini_date, p_fim_date

    periodo_invalido = False
    if d_ini > d_fim:
        st.sidebar.error("Data inicial não pode ser posterior à data final.")
        periodo_invalido = True

    periodo_tuple = (d_ini.strftime("%Y-%m-%d"), d_fim.strftime("%Y-%m-%d"))

    todos_indicadores = list(BACEN_SERIES.keys())
    indicadores_salvos = [
        i for i in f_state.get("indicadores_bacen", []) if i in todos_indicadores
    ]

    indicadores_selecionados = st.sidebar.multiselect(
        "Indicadores BACEN (Opcionais)",
        options=todos_indicadores,
        default=indicadores_salvos,
        help="Controla séries macroeconômicas secundárias nos gráficos e tabelas do Dashboard 1.",
    )

    st.sidebar.button(
        "🧹 Resetar filtros",
        on_click=reset_filtros,
        help="Restaura todos os filtros globais para as configurações padrão.",
    )

    n_empresas = len(tickers_selecionados)
    n_setores = len(setores_selecionados) if setores_selecionados else len(todos_setores)
    ano_ini = d_ini.strftime("%Y")
    ano_fim = d_fim.strftime("%Y")
    resumo_header = f"{n_empresas} empresas · {n_setores} setores · {ano_ini}-{ano_fim}"

    st.sidebar.markdown(f"**Resumo:** `{resumo_header}`")

    if not tickers_selecionados:
        st.sidebar.warning("Selecione ao menos um ativo/empresa para carregar o dashboard.")

    st.session_state["filtros"] = {
        "periodo": periodo_tuple,
        "tickers": tickers_selecionados,
        "setores": setores_selecionados,
        "indicadores_bacen": indicadores_selecionados,
    }

    return montar_filtros()