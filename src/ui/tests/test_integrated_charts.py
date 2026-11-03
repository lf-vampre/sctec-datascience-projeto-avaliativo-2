"""Testes unitários para os gráficos Plotly do Dashboard Integrado (integrated_charts)."""

import pandas as pd
import plotly.graph_objects as go
import pytest

from src.ui.charts.integrated_charts import (
    fig_barras_contabeis,
    fig_base100,
    fig_dispersao_ebit_retorno,
    fig_efeito_aperto,
    fig_exportadoras_estresse,
    fig_macro_cambial,
    fig_ranking_setorial,
    fig_setorial_vs_selic,
)


@pytest.fixture
def painel_mensal_mock() -> pd.DataFrame:
    datas = pd.date_range("2021-01-01", "2021-12-31", freq="MS")
    idx = datas.strftime("%Y-%m")
    return pd.DataFrame(
        {
            "SELIC_META": [2.0 + i * 0.5 for i in range(12)],
            "IPCA_12M": [4.5 + i * 0.1 for i in range(12)],
            "PTAX_VENDA": [5.2 + i * 0.05 for i in range(12)],
        },
        index=idx,
    )


@pytest.fixture
def painel_cvm_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "tipo_plano": "industrial",
            "exportadora_commodities": True,
            "ano": 2022,
            "comparavel_receita": True,
            "RECEITA_LIQUIDA": 120000.0,
            "LUCRO_LIQUIDO": 25000.0,
            "ROE": 0.22,
        },
        {
            "ticker": "ITUB4",
            "setor_analitico": "Financeiro",
            "tipo_plano": "financeira",
            "exportadora_commodities": False,
            "ano": 2022,
            "comparavel_receita": False,
            "RECEITA_LIQUIDA": None,
            "LUCRO_LIQUIDO": 30000.0,
            "ROE": 0.18,
        },
    ])


@pytest.fixture
def tabela_setorial_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ano": 2021,
            "setor_analitico": "Materiais Básicos",
            "retorno_setorial_pct": 15.0,
            "selic_media_pct": 4.25,
            "ipca_12m_dec_pct": 10.06,
            "flag_parcial": True,
        },
        {
            "ano": 2022,
            "setor_analitico": "Materiais Básicos",
            "retorno_setorial_pct": -5.0,
            "selic_media_pct": 12.38,
            "ipca_12m_dec_pct": 5.79,
            "flag_parcial": False,
        },
        {
            "ano": 2021,
            "setor_analitico": "Financeiro",
            "retorno_setorial_pct": 8.0,
            "selic_media_pct": 4.25,
            "ipca_12m_dec_pct": 10.06,
            "flag_parcial": True,
        },
        {
            "ano": 2022,
            "setor_analitico": "Financeiro",
            "retorno_setorial_pct": 12.0,
            "selic_media_pct": 12.38,
            "ipca_12m_dec_pct": 5.79,
            "flag_parcial": False,
        },
    ])


@pytest.fixture
def df_dispersao_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "exportadora_commodities": True,
            "receita_liquida": 120000.0,
            "margem_ebit": 0.30,
            "retorno_acumulado_pct": 25.0,
        },
        {
            "ticker": "WEGE3",
            "setor_analitico": "Indústria & Bens de Capital",
            "exportadora_commodities": False,
            "receita_liquida": 30000.0,
            "margem_ebit": 0.18,
            "retorno_acumulado_pct": 10.0,
        },
    ])


@pytest.fixture
def tabela_aperto_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ano": 2021,
            "despesa_financeira_total": 500.0,
            "despesa_financeira_b100": 100.0,
            "lucro_liquido_total": 2000.0,
            "lucro_liquido_b100": 100.0,
            "alavancagem_media": 0.4,
            "selic_media_anual": 4.25,
        },
        {
            "ano": 2022,
            "despesa_financeira_total": 800.0,
            "despesa_financeira_b100": 160.0,
            "lucro_liquido_total": 2200.0,
            "lucro_liquido_b100": 110.0,
            "alavancagem_media": 0.45,
            "selic_media_anual": 12.38,
        },
    ])


@pytest.fixture
def df_estresse_ret_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "grupo": "Exportadoras Commodities",
            "retorno_diario_medio_dentro_pct": 0.15,
            "retorno_diario_medio_fora_pct": 0.05,
            "diferenca_pp": 0.10,
        },
        {
            "grupo": "Demais Setores",
            "retorno_diario_medio_dentro_pct": -0.05,
            "retorno_diario_medio_fora_pct": 0.02,
            "diferenca_pp": -0.07,
        },
    ])


@pytest.fixture
def df_estresse_margem_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ano": 2021,
            "margem_ebit_exportadoras_pct": 25.0,
            "margem_ebit_demais_pct": 15.0,
            "ptax_media_anual": 5.39,
        },
        {
            "ano": 2022,
            "margem_ebit_exportadoras_pct": 30.0,
            "margem_ebit_demais_pct": 14.0,
            "ptax_media_anual": 5.16,
        },
    ])


@pytest.fixture
def df_ranking_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "setor_analitico": "Materiais Básicos",
            "pilar_bolsa_score": 80.0,
            "pilar_resiliencia_score": 75.0,
            "pilar_solidez_score": 85.0,
            "score_final": 80.0,
            "flag_parcial": False,
        },
        {
            "setor_analitico": "Financeiro",
            "pilar_bolsa_score": 60.0,
            "pilar_resiliencia_score": 70.0,
            "pilar_solidez_score": 65.0,
            "score_final": 65.0,
            "flag_parcial": True,
        },
    ])


def test_fig_macro_cambial(painel_mensal_mock):
    fig = fig_macro_cambial(painel_mensal_mock)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3
    # Verifica eixo secundario presente na PTAX
    assert fig.data[2].yaxis == "y2"


def test_fig_barras_contabeis(painel_cvm_mock):
    fig = fig_barras_contabeis(painel_cvm_mock, 2022)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    # Presença de bancos no Lucro e ROE
    tickers_lucro = list(fig.data[0].y)
    tickers_roe = list(fig.data[1].y)
    assert "ITUB4" in tickers_lucro
    assert "ITUB4" in tickers_roe


def test_fig_setorial_vs_selic(tabela_setorial_mock):
    fig = fig_setorial_vs_selic(tabela_setorial_mock)
    assert isinstance(fig, go.Figure)
    # 2 barras setoriais + 1 linha Selic = 3 traços
    assert len(fig.data) == 3
    assert fig.data[2].yaxis == "y2"


def test_fig_dispersao_ebit_retorno(df_dispersao_mock):
    fig = fig_dispersao_ebit_retorno(df_dispersao_mock)
    assert isinstance(fig, go.Figure)
    # Ausência de bancos na dispersão
    for trace in fig.data:
        if hasattr(trace, "text") and trace.text is not None:
            assert "ITUB4" not in trace.text


def test_fig_efeito_aperto(tabela_aperto_mock):
    fig = fig_efeito_aperto(tabela_aperto_mock)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 4


def test_fig_exportadoras_estresse(df_estresse_ret_mock, df_estresse_margem_mock):
    fig = fig_exportadoras_estresse(df_estresse_ret_mock, df_estresse_margem_mock)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 4


def test_fig_ranking_setorial(df_ranking_mock):
    fig = fig_ranking_setorial(df_ranking_mock)
    assert len(fig.data) >= 3


def test_figuras_vazias():
    fig_m = fig_macro_cambial(pd.DataFrame())
    assert len(fig_m.data) == 0

    fig_c = fig_barras_contabeis(pd.DataFrame(), 2022)
    assert len(fig_c.data) == 0

    fig_s = fig_setorial_vs_selic(pd.DataFrame())
    assert len(fig_s.data) == 0

    fig_d = fig_dispersao_ebit_retorno(pd.DataFrame())
    assert len(fig_d.data) == 0

    fig_a = fig_efeito_aperto(pd.DataFrame())
    assert len(fig_a.data) == 0

    fig_e = fig_exportadoras_estresse(pd.DataFrame(), pd.DataFrame())
    assert len(fig_e.data) == 0

    fig_r = fig_ranking_setorial(pd.DataFrame())
    assert len(fig_r.data) == 0


def test_ausencia_de_textos_causais(painel_mensal_mock, painel_cvm_mock, tabela_setorial_mock):
    figuras = [
        fig_macro_cambial(painel_mensal_mock),
        fig_barras_contabeis(painel_cvm_mock, 2022),
        fig_setorial_vs_selic(tabela_setorial_mock),
    ]

    palavras_proibidas = ["impactou", "afetou", "causou", "provocou"]

    for fig in figuras:
        layout_str = str(fig.layout).lower()
        for palavra in palavras_proibidas:
            assert palavra not in layout_str, f"Termo causal proibido '{palavra}' encontrado no layout da figura."