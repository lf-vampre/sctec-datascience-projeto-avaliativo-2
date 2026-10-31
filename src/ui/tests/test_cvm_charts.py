"""Testes unitários para as figuras Plotly do Dashboard Fundamentalista CVM."""

import pandas as pd
import pytest
import plotly.graph_objects as go

from src.ui.charts.cvm_charts import (
    fig_receita_agrupada,
    fig_donut_setorial,
    fig_margem_roe,
    fig_boxplot_ebit,
    fig_solvencia,
    fig_margem_evolucao,
)


@pytest.fixture
def mock_painel() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "ano": 2022,
            "comparavel_receita": True,
            "exportadora_commodities": True,
            "RECEITA_LIQUIDA": 1000.0,
            "RECEITA_INTERMEDIACAO": None,
            "MARGEM_LIQUIDA": 20.0,
            "ROE": 15.0,
            "MARGEM_EBIT": 30.0,
            "LIQUIDEZ_CORRENTE": 1.8,
            "DIVIDA_LIQUIDA": -50.0,
            "atencao_liquidez": False,
        },
        {
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "ano": 2023,
            "comparavel_receita": True,
            "exportadora_commodities": True,
            "RECEITA_LIQUIDA": 1200.0,
            "RECEITA_INTERMEDIACAO": None,
            "MARGEM_LIQUIDA": 22.0,
            "ROE": 18.0,
            "MARGEM_EBIT": 32.0,
            "LIQUIDEZ_CORRENTE": 2.0,
            "DIVIDA_LIQUIDA": 100.0,
            "atencao_liquidez": False,
        },
        {
            "ticker": "ITUB4",
            "setor_analitico": "Financeiro",
            "ano": 2023,
            "comparavel_receita": False,
            "exportadora_commodities": False,
            "RECEITA_LIQUIDA": None,
            "RECEITA_INTERMEDIACAO": 5000.0,
            "MARGEM_LIQUIDA": None,
            "ROE": 20.0,
            "MARGEM_EBIT": None,
            "LIQUIDEZ_CORRENTE": None,
            "DIVIDA_LIQUIDA": None,
            "atencao_liquidez": False,
        },
    ])


def test_fig_receita_agrupada(mock_painel):
    fig = fig_receita_agrupada(mock_painel)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_fig_receita_agrupada_vazia():
    fig = fig_receita_agrupada(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_fig_donut_setorial():
    dist = {
        "setores": pd.DataFrame([
            {"setor_analitico": "Materiais Básicos", "RECEITA_LIQUIDA": 1200.0, "participacao_pct": 100.0}
        ])
    }
    fig = fig_donut_setorial(dist)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].type == "pie"


def test_fig_donut_setorial_vazio():
    fig = fig_donut_setorial({})
    assert isinstance(fig, go.Figure)


def test_fig_margem_roe():
    dispersao = {
        "pontos": pd.DataFrame([
            {
                "ticker": "VALE3",
                "setor_analitico": "Materiais Básicos",
                "RECEITA_LIQUIDA": 1200.0,
                "MARGEM_LIQUIDA": 20.0,
                "ROE": 18.0,
                "quadrante": "Líder (Margem Alta / ROE Alto)",
            }
        ]),
        "mediana_margem": 15.0,
        "mediana_roe": 10.0,
    }
    fig = fig_margem_roe(dispersao)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_fig_margem_roe_vazio():
    fig = fig_margem_roe({})
    assert isinstance(fig, go.Figure)


def test_fig_boxplot_ebit():
    df_dist = pd.DataFrame([
        {"ticker": "VALE3", "ano": 2023, "grupo": "Materiais Básicos", "MARGEM_EBIT": 30.0}
    ])
    fig = fig_boxplot_ebit(df_dist)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_fig_boxplot_ebit_vazio():
    fig = fig_boxplot_ebit(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_fig_solvencia():
    solv_df = pd.DataFrame([
        {
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "DIVIDA_LIQUIDA": 100.0,
            "LIQUIDEZ_CORRENTE": 2.0,
            "atencao_liquidez": False,
            "caixa_liquido": False,
        }
    ])
    fig = fig_solvencia(solv_df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_fig_solvencia_vazia():
    fig = fig_solvencia(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_fig_margem_evolucao():
    margens = pd.DataFrame([
        {"ticker": "VALE3", "setor_analitico": "Materiais Básicos", "ano": 2022, "MARGEM_LIQUIDA": 20.0},
        {"ticker": "VALE3", "setor_analitico": "Materiais Básicos", "ano": 2023, "MARGEM_LIQUIDA": 22.0},
    ])
    fig = fig_margem_evolucao(margens)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_fig_margem_evolucao_vazia():
    fig = fig_margem_evolucao(pd.DataFrame())
    assert isinstance(fig, go.Figure)