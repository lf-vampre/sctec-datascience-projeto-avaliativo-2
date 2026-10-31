"""Testes unitários para preparação de dados do Dashboard de Mercado e Risco (market_prep)."""

import numpy as np
import pandas as pd
import pytest

from src.ui.prep.market_prep import (
    _preparar_pivots,
    calcular_base100,
    distribuicao_retornos,
    extrair_rf_diaria,
    kpis_mercado,
    ranking_resiliencia,
    serie_drawdown,
    serie_sma,
    tabela_risco_retorno,
)


@pytest.fixture
def mock_cotacoes_empresas() -> tuple[pd.DataFrame, pd.DataFrame]:
    datas = pd.date_range("2022-01-01", periods=10, freq="B")
    df_cot = []
    for d in datas:
        sk_t = int(d.strftime("%Y%m%d"))
        df_cot.append({
            "sk_tempo": sk_t,
            "sk_empresa": 1,
            "close": 10.0 + (sk_t % 5),
            "volume": 1000,
            "volume_fin_aprox": (10.0 + (sk_t % 5)) * 1000,
            "sma_21": np.nan,
            "sma_50": np.nan,
        })
        df_cot.append({
            "sk_tempo": sk_t,
            "sk_empresa": 2,
            "close": 20.0 - (sk_t % 3),
            "volume": 2000,
            "volume_fin_aprox": (20.0 - (sk_t % 3)) * 2000,
            "sma_21": np.nan,
            "sma_50": np.nan,
        })

    df_emp = pd.DataFrame([
        {"sk_empresa": 1, "ticker": "PETR4"},
        {"sk_empresa": 2, "ticker": "VALE3"},
    ])

    return pd.DataFrame(df_cot), df_emp


def test_preparar_pivots(mock_cotacoes_empresas):
    df_cot, df_emp = mock_cotacoes_empresas
    p_close, p_vol_fin, p_ret = _preparar_pivots(df_cot, df_emp)

    assert not p_close.empty
    assert "PETR4" in p_close.columns
    assert "VALE3" in p_close.columns
    assert len(p_close) == 10


def test_calcular_base100_inicia_em_100():
    datas = pd.date_range("2023-01-01", periods=5, freq="B")
    pivot_close = pd.DataFrame(
        {"PETR4": [10.0, 11.0, 10.5, 12.0, 12.5]},
        index=datas,
    )
    b100, avisos = calcular_base100(pivot_close)

    assert b100.iloc[0]["PETR4"] == 100.0
    assert "Carteira" in b100.columns
    assert b100.iloc[0]["Carteira"] == 100.0
    assert len(avisos) == 0


def test_calcular_base100_ativo_sem_dados():
    datas = pd.date_range("2023-01-01", periods=5, freq="B")
    pivot_close = pd.DataFrame(
        {"PETR4": [10.0, 11.0, 12.0, 13.0, 14.0], "VALE3": [np.nan] * 5},
        index=datas,
    )
    b100, avisos = calcular_base100(pivot_close)

    assert "VALE3 sem cotações válidas" in avisos[0]


def test_tabela_risco_retorno_e_injecao_rf():
    datas = pd.date_range("2023-01-01", periods=10, freq="B")
    p_close = pd.DataFrame({"PETR4": [10.0 + i for i in range(10)]}, index=datas)
    p_vol = pd.DataFrame({"PETR4": [1000.0] * 10}, index=datas)
    p_ret = p_close.pct_change(fill_method=None)

    rf_zero = pd.Series(0.0, index=datas)
    rf_alta = pd.Series(0.15, index=datas)

    tabela_rf0 = tabela_risco_retorno(p_close, p_vol, p_ret, rf_zero)
    tabela_rf15 = tabela_risco_retorno(p_close, p_vol, p_ret, rf_alta)

    sh0 = tabela_rf0[tabela_rf0["ticker"] == "PETR4"].iloc[0]["sharpe"]
    sh15 = tabela_rf15[tabela_rf15["ticker"] == "PETR4"].iloc[0]["sharpe"]

    assert sh0 != sh15


def test_drawdown_serie_construida():
    datas = pd.date_range("2023-01-01", periods=4, freq="B")
    p_close = pd.DataFrame({"PETR4": [100.0, 120.0, 90.0, 108.0]}, index=datas)

    dd_df = serie_drawdown(p_close)
    # Pico no 2º dia = 120; no 3º dia 90 -> dd = (90-120)/120 = -0.25
    assert pytest.approx(dd_df.iloc[2]["PETR4"], 0.001) == -0.25


def test_kpis_mercado_delta_anual():
    datas_2022 = pd.date_range("2022-01-01", "2022-12-31", freq="B")
    datas_2023 = pd.date_range("2023-01-01", "2023-12-31", freq="B")
    all_datas = datas_2022.append(datas_2023)

    p_close = pd.DataFrame(
        {"PETR4": np.linspace(10, 20, len(all_datas))},
        index=all_datas,
    )
    p_vol = pd.DataFrame({"PETR4": [1000.0] * len(all_datas)}, index=all_datas)
    p_ret = p_close.pct_change(fill_method=None)

    tabela = tabela_risco_retorno(p_close, p_vol, p_ret)
    kpis = kpis_mercado(tabela, p_close)

    assert kpis["retorno_medio_carteira"] is not None
    assert kpis["ativo_destaque"] == "PETR4"
    assert kpis["retorno_delta_pp"] is not None


def test_distribuicao_retornos():
    datas = pd.date_range("2023-01-01", periods=10, freq="B")
    p_ret = pd.DataFrame({"PETR4": np.random.normal(0.001, 0.02, 10)}, index=datas)

    serie, stats = distribuicao_retornos(p_ret, "PETR4")
    assert len(serie) == 10
    assert "assimetria" in stats
    assert "curtose" in stats
    assert "p5" in stats


def test_ranking_resiliencia():
    tabela = pd.DataFrame([
        {"ticker": "PETR4", "drawdown_maximo": -0.30},
        {"ticker": "VALE3", "drawdown_maximo": -0.15},
        {"ticker": "Carteira", "drawdown_maximo": -0.20},
    ])
    res = ranking_resiliencia(tabela)

    assert res.iloc[0]["ticker"] == "VALE3"
    assert "Carteira" not in res["ticker"].values


def test_serie_sma(mock_cotacoes_empresas):
    df_cot, df_emp = mock_cotacoes_empresas
    df_sma = serie_sma(df_cot, df_emp, "PETR4")

    assert not df_sma.empty
    assert "close" in df_sma.columns
    assert "sma_21" in df_sma.columns
    assert "sma_50" in df_sma.columns
    assert "cruzamento" in df_sma.columns


def test_extrair_rf_diaria_ausente():
    fato_macro = pd.DataFrame()
    dim_ind = pd.DataFrame()
    datas = pd.date_range("2023-01-01", periods=5, freq="B")

    rf, avisos = extrair_rf_diaria(fato_macro, dim_ind, datas)
    assert rf is None
    assert len(avisos) > 0