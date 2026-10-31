"""Testes unitários para visualizações Plotly do Dashboard de Mercado e Risco (market_charts)."""

import numpy as np
import pandas as pd
import pytest

from src.ui.charts.market_charts import (
    fig_base100,
    fig_drawdown,
    fig_hist_retornos,
    fig_risco_retorno,
    fig_sma,
)


@pytest.fixture
def mock_base100_df() -> pd.DataFrame:
    datas = pd.date_range("2023-01-01", periods=10, freq="B")
    return pd.DataFrame(
        {
            "PETR4": np.linspace(100, 120, 10),
            "VALE3": np.linspace(100, 90, 10),
            "Carteira": np.linspace(100, 105, 10),
        },
        index=datas,
    )


@pytest.fixture
def mock_tabela_rr() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": "PETR4",
            "volatilidade_anualizada": 0.25,
            "retorno_acumulado": 0.15,
            "sharpe": 0.60,
            "drawdown_maximo": -0.10,
            "volume_medio_diario": 50_000_000.0,
        },
        {
            "ticker": "VALE3",
            "volatilidade_anualizada": 0.20,
            "retorno_acumulado": 0.05,
            "sharpe": 0.25,
            "drawdown_maximo": -0.12,
            "volume_medio_diario": 30_000_000.0,
        },
        {
            "ticker": "Carteira",
            "volatilidade_anualizada": 0.18,
            "retorno_acumulado": 0.10,
            "sharpe": 0.50,
            "drawdown_maximo": -0.08,
            "volume_medio_diario": 80_000_000.0,
        },
    ])


@pytest.fixture
def mock_df_sma() -> pd.DataFrame:
    datas = pd.date_range("2023-01-01", periods=60, freq="B")
    close = np.sin(np.linspace(0, 10, 60)) * 5 + 30
    sma_21 = pd.Series(close).rolling(21).mean().values
    sma_50 = pd.Series(close).rolling(50).mean().values
    cruz = ["Neutro"] * 60
    cruz[50] = "SMA 21 cruzou acima da SMA 50"

    return pd.DataFrame(
        {
            "close": close,
            "sma_21": sma_21,
            "sma_50": sma_50,
            "cruzamento": cruz,
        },
        index=datas,
    )


def test_fig_base100_estruturas_e_linha_referencia(mock_base100_df):
    fig = fig_base100(mock_base100_df)

    assert fig is not None
    assert len(fig.data) == 3  # PETR4, VALE3, Carteira
    # Verifica presença da linha horizontal de referência no nível 100
    shapes = fig.layout.shapes
    assert any(getattr(s, "y0", None) == 100.0 for s in shapes)


def test_fig_base100_destaque_ativo(mock_base100_df):
    fig = fig_base100(mock_base100_df, destacar="PETR4")
    trace_petr = [t for t in fig.data if t.name == "PETR4"][0]
    trace_vale = [t for t in fig.data if t.name == "VALE3"][0]

    assert trace_petr.opacity == 1.0
    assert trace_vale.opacity == 0.2


def test_fig_base100_vazio():
    fig = fig_base100(pd.DataFrame())
    assert fig is not None
    assert len(fig.data) == 0


def test_fig_risco_retorno(mock_tabela_rr):
    fig = fig_risco_retorno(mock_tabela_rr)

    assert fig is not None
    assert len(fig.data) > 0
    # Checa presenças de vline e hline de mediana no layout
    shapes = fig.layout.shapes
    assert len(shapes) >= 2


def test_fig_risco_retorno_vazio():
    fig = fig_risco_retorno(pd.DataFrame())
    assert fig is not None
    assert len(fig.data) == 0


def test_fig_hist_retornos():
    np.random.seed(42)
    ret = pd.Series(np.random.normal(0.001, 0.02, 100))
    stats = {"p5": -0.03, "assimetria": 0.1, "curtose": 0.2}

    fig = fig_hist_retornos(ret, stats, "PETR4")

    assert fig is not None
    # px.histogram com marginal='box' cria múltiplos traços (histograma + boxplot)
    assert len(fig.data) >= 2


def test_fig_hist_retornos_vazio():
    fig = fig_hist_retornos(pd.Series(dtype=float), {})
    assert fig is not None
    assert len(fig.data) == 0


def test_fig_drawdown():
    datas = pd.date_range("2023-01-01", periods=5, freq="B")
    df_dd = pd.DataFrame(
        {
            "PETR4": [0.0, -0.05, -0.10, -0.02, 0.0],
            "Carteira": [0.0, -0.02, -0.05, -0.01, 0.0],
        },
        index=datas,
    )

    fig = fig_drawdown(df_dd, selecionados=["PETR4", "Carteira"])

    assert fig is not None
    assert len(fig.data) == 2
    # Drawdown em % nunca deve possuir valores estritamente positivos no mock
    for trace in fig.data:
        assert all(y <= 0.0 for y in trace.y)


def test_fig_drawdown_vazio():
    fig = fig_drawdown(pd.DataFrame())
    assert fig is not None
    assert len(fig.data) == 0


def test_fig_sma(mock_df_sma):
    fig = fig_sma(mock_df_sma, ticker="PETR4")

    assert fig is not None
    # Deve conter fecho + sma_21 + sma_50 + evento de cruzamento (4 traços no total)
    assert len(fig.data) == 4
    niveis = [t.name for t in fig.data]
    assert "Fechamento" in niveis
    assert "SMA 21 (Curto Prazo)" in niveis
    assert "SMA 50 (Médio Prazo)" in niveis


def test_fig_sma_vazio():
    fig = fig_sma(pd.DataFrame(), ticker="PETR4")
    assert fig is not None
    assert len(fig.data) == 0