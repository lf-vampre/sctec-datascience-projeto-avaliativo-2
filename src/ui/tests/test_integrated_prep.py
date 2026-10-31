"""Testes unitários para a preparação de dados do Dashboard Integrado (integrated_prep)."""

import numpy as np
import pandas as pd
import pytest

from src.ui.prep.integrated_prep import (
    dispersao_ebit_retorno,
    kpis_triade,
    painel_macro_cambial,
    retorno_setorial_vs_selic,
    universo_triade,
)


@pytest.fixture
def dim_empresa_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "sk_empresa": 1,
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "tipo_plano": "industrial",
            "exportadora_commodities": True,
            "tem_cvm": True,
            "tem_b3": True,
        },
        {
            "sk_empresa": 2,
            "ticker": "ITUB4",
            "setor_analitico": "Financeiro",
            "tipo_plano": "financeira",
            "exportadora_commodities": False,
            "tem_cvm": True,
            "tem_b3": True,
        },
        {
            "sk_empresa": 3,
            "ticker": "FORA1",
            "setor_analitico": "Outros",
            "tipo_plano": "industrial",
            "exportadora_commodities": False,
            "tem_cvm": True,
            "tem_b3": False,
        },
    ])


@pytest.fixture
def fato_macro_mock() -> pd.DataFrame:
    datas = pd.date_range("2021-01-01", "2022-12-31", freq="D")
    rows = []
    for d in datas:
        sk = int(d.strftime("%Y%m%d"))
        rows.append({"sk_tempo": sk, "sk_indicador": 1, "valor": 10.0, "data": d.strftime("%Y-%m-%d")})
        rows.append({"sk_tempo": sk, "sk_indicador": 2, "valor": 5.0, "data": d.strftime("%Y-%m-%d")})
        rows.append({"sk_tempo": sk, "sk_indicador": 3, "valor": 5.20, "data": d.strftime("%Y-%m-%d")})
    return pd.DataFrame(rows)


@pytest.fixture
def dim_indicador_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {"sk_indicador": 1, "codigo": "SELIC_META", "agg_mensal": "ultimo"},
        {"sk_indicador": 2, "codigo": "IPCA_12M", "agg_mensal": "ultimo"},
        {"sk_indicador": 3, "codigo": "PTAX_VENDA", "agg_mensal": "media"},
    ])


@pytest.fixture
def fato_cotacoes_mock() -> pd.DataFrame:
    datas = pd.date_range("2021-01-04", "2022-12-30", freq="B")
    rows = []
    for d in datas:
        sk = int(d.strftime("%Y%m%d"))
        rows.append({"sk_tempo": sk, "sk_empresa": 1, "close": 100.0 + (d.dayofyear * 0.1), "volume": 1000})
        rows.append({"sk_tempo": sk, "sk_empresa": 2, "close": 20.0 + (d.dayofyear * 0.02), "volume": 500})
    return pd.DataFrame(rows)


@pytest.fixture
def painel_cvm_mock() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "tipo_plano": "industrial",
            "exportadora_commodities": True,
            "ano": 2021,
            "comparavel_receita": True,
            "RECEITA_LIQUIDA": 1000.0,
            "LUCRO_LIQUIDO": 200.0,
            "MARGEM_EBIT": 0.25,
            "ROE": 0.20,
            "LIQUIDEZ_CORRENTE": 1.5,
        },
        {
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "tipo_plano": "industrial",
            "exportadora_commodities": True,
            "ano": 2022,
            "comparavel_receita": True,
            "RECEITA_LIQUIDA": 1200.0,
            "LUCRO_LIQUIDO": 250.0,
            "MARGEM_EBIT": 0.30,
            "ROE": 0.22,
            "LIQUIDEZ_CORRENTE": 1.6,
        },
        {
            "ticker": "ITUB4",
            "setor_analitico": "Financeiro",
            "tipo_plano": "financeira",
            "exportadora_commodities": False,
            "ano": 2021,
            "comparavel_receita": False,
            "RECEITA_LIQUIDA": np.nan,
            "LUCRO_LIQUIDO": 500.0,
            "MARGEM_EBIT": np.nan,
            "ROE": 0.18,
            "LIQUIDEZ_CORRENTE": np.nan,
        },
        {
            "ticker": "ITUB4",
            "setor_analitico": "Financeiro",
            "tipo_plano": "financeira",
            "exportadora_commodities": False,
            "ano": 2022,
            "comparavel_receita": False,
            "RECEITA_LIQUIDA": np.nan,
            "LUCRO_LIQUIDO": 600.0,
            "MARGEM_EBIT": np.nan,
            "ROE": 0.19,
            "LIQUIDEZ_CORRENTE": np.nan,
        },
    ])


def test_universo_triade(dim_empresa_mock):
    df_triade, avisos = universo_triade(dim_empresa_mock)
    assert len(df_triade) == 2
    assert set(df_triade["ticker"]) == {"VALE3", "ITUB4"}
    assert len(avisos) == 1
    assert "FORA1" in avisos[0]


def test_kpis_triade(fato_macro_mock, dim_indicador_mock, painel_cvm_mock):
    kpis, avisos = kpis_triade(fato_macro_mock, dim_indicador_mock, painel_cvm_mock, 2022)
    assert kpis["selic_vigente"] == 10.0
    assert kpis["ipca_12m"] == 5.0
    assert kpis["receita_consolidada"] == 1200.0
    assert kpis["lucro_consolidado"] == 850.0
    assert any("exclui 1 instituição(ões) financeira(s)" in a for a in avisos)


def test_painel_macro_cambial(fato_macro_mock, dim_indicador_mock):
    pm = painel_macro_cambial(fato_macro_mock, dim_indicador_mock)
    assert not pm.empty
    assert "SELIC_META" in pm.columns
    assert "IPCA_12M" in pm.columns
    assert "PTAX_VENDA" in pm.columns


def test_retorno_setorial_vs_selic(fato_macro_mock, dim_indicador_mock, fato_cotacoes_mock, dim_empresa_mock):
    df_ret, avisos = retorno_setorial_vs_selic(fato_macro_mock, dim_indicador_mock, fato_cotacoes_mock, dim_empresa_mock)
    assert not df_ret.empty
    assert set(df_ret["setor_analitico"]) == {"Materiais Básicos", "Financeiro"}
    row_2021 = df_ret[df_ret["ano"] == 2021].iloc[0]
    assert bool(row_2021["flag_parcial"]) is True
    assert any("parcial" in a for a in avisos)


def test_dispersao_ebit_retorno_sem_bancos(painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock):
    df_disp, avisos = dispersao_ebit_retorno(painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock, ano_foco=2022)
    assert not df_disp.empty
    assert "ITUB4" not in df_disp["ticker"].values
    assert "VALE3" in df_disp["ticker"].values
    row_vale = df_disp[df_disp["ticker"] == "VALE3"].iloc[0]
    assert row_vale["margem_ebit"] == 0.30


def test_dispersao_ebit_retorno_periodo(painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock):
    df_disp, _ = dispersao_ebit_retorno(painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock, periodo=(2021, 2022))
    assert not df_disp.empty
    assert "ITUB4" not in df_disp["ticker"].values
    row_vale = df_disp[df_disp["ticker"] == "VALE3"].iloc[0]
    assert pytest.approx(row_vale["margem_ebit"]) == 0.275


def test_entradas_vazias():
    df_disp, avisos = dispersao_ebit_retorno(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert df_disp.empty
    assert len(avisos) > 0