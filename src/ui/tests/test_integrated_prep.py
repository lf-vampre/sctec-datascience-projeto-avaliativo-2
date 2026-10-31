"""Testes unitários para a preparação de dados do Dashboard Integrado (integrated_prep)."""

import numpy as np
import pandas as pd
import pytest

from src.ui.prep.integrated_prep import (
    dispersao_ebit_retorno,
    efeito_aperto,
    exportadoras_em_estresse,
    janelas_estresse_cambial,
    kpis_triade,
    margem_ebit_exportadoras,
    painel_macro_cambial,
    ranking_setorial,
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
        # PTAX com rampa de estresse em mar/2021 (de 5.0 para 6.0)
        ptax_val = 6.0 if (d.year == 2021 and d.month == 3) else 5.0
        rows.append({"sk_tempo": sk, "sk_indicador": 3, "valor": ptax_val, "data": d.strftime("%Y-%m-%d")})
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
            "DESPESAS_FINANCEIRAS": 50.0,
            "MARGEM_EBIT": 0.25,
            "ROE": 0.20,
            "LIQUIDEZ_CORRENTE": 1.5,
            "DIVIDA_LIQUIDA": 100.0,
            "PATRIMONIO_LIQUIDO": 500.0,
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
            "DESPESAS_FINANCEIRAS": 80.0,
            "MARGEM_EBIT": 0.30,
            "ROE": 0.22,
            "LIQUIDEZ_CORRENTE": 1.6,
            "DIVIDA_LIQUIDA": 120.0,
            "PATRIMONIO_LIQUIDO": 600.0,
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
            "DESPESAS_FINANCEIRAS": np.nan,
            "MARGEM_EBIT": np.nan,
            "ROE": 0.18,
            "LIQUIDEZ_CORRENTE": np.nan,
            "DIVIDA_LIQUIDA": np.nan,
            "PATRIMONIO_LIQUIDO": 2000.0,
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
            "DESPESAS_FINANCEIRAS": np.nan,
            "MARGEM_EBIT": np.nan,
            "ROE": 0.19,
            "LIQUIDEZ_CORRENTE": np.nan,
            "DIVIDA_LIQUIDA": np.nan,
            "PATRIMONIO_LIQUIDO": 2200.0,
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


def test_efeito_aperto(painel_cvm_mock, fato_macro_mock, dim_indicador_mock):
    df_aperto, avisos = efeito_aperto(painel_cvm_mock, fato_macro_mock, dim_indicador_mock, ano_base=2021)
    assert not df_aperto.empty
    assert "despesa_financeira_b100" in df_aperto.columns
    row_2021 = df_aperto[df_aperto["ano"] == 2021].iloc[0]
    row_2022 = df_aperto[df_aperto["ano"] == 2022].iloc[0]
    assert row_2021["despesa_financeira_b100"] == 100.0
    assert row_2022["despesa_financeira_b100"] == 160.0  # 80 / 50 * 100
    assert pytest.approx(row_2021["alavancagem_media"]) == 0.20  # 100 / 500


def test_efeito_aperto_pl_negativo(painel_cvm_mock, fato_macro_mock, dim_indicador_mock):
    painel_mod = painel_cvm_mock.copy()
    painel_mod.loc[painel_mod["ticker"] == "VALE3", "PATRIMONIO_LIQUIDO"] = -100.0
    df_aperto, avisos = efeito_aperto(painel_mod, fato_macro_mock, dim_indicador_mock, ano_base=2021)
    assert not df_aperto.empty
    assert any("PL <= 0" in a for a in avisos)


def test_janelas_estresse_cambial():
    datas = pd.date_range("2021-01-01", "2021-03-31", freq="D")
    valores = [5.0] * len(datas)
    # Pico de estresse no final de janeiro (5.0 -> 5.5 = +10%)
    for i, d in enumerate(datas):
        if d.month == 1 and d.day >= 20:
            valores[i] = 5.5
    s_ptax = pd.Series(valores, index=datas)

    df_estresse = janelas_estresse_cambial(s_ptax, janela_dias=30, limiar_pct=5.0)
    assert not df_estresse.empty
    assert float(df_estresse.iloc[0]["variacao_pct"]) >= 5.0


def test_exportadoras_em_estresse(fato_cotacoes_mock, dim_empresa_mock):
    janelas = pd.DataFrame([
        {"inicio": pd.Timestamp("2021-03-01"), "fim": pd.Timestamp("2021-03-31"), "variacao_pct": 20.0}
    ])
    df_exp, avisos = exportadoras_em_estresse(fato_cotacoes_mock, dim_empresa_mock, janelas)
    assert not df_exp.empty
    assert "Exportadoras Commodities" in df_exp["grupo"].values


def test_margem_ebit_exportadoras(painel_cvm_mock, fato_macro_mock, dim_indicador_mock):
    df_m, avisos = margem_ebit_exportadoras(painel_cvm_mock, fato_macro_mock, dim_indicador_mock)
    assert not df_m.empty
    assert "margem_ebit_exportadoras_pct" in df_m.columns
    row_2021 = df_m[df_m["ano"] == 2021].iloc[0]
    assert pytest.approx(row_2021["margem_ebit_exportadoras_pct"]) == 25.0


def test_ranking_setorial(painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock, fato_macro_mock, dim_indicador_mock):
    df_rank, avisos = ranking_setorial(
        painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock, fato_macro_mock, dim_indicador_mock
    )
    assert not df_rank.empty
    assert "score_final" in df_rank.columns
    fin_row = df_rank[df_rank["setor_analitico"] == "Financeiro"].iloc[0]
    assert bool(fin_row["flag_parcial"]) is True
    assert any("parcial" in a for a in avisos)


def test_ranking_setorial_alteracao_pesos(painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock, fato_macro_mock, dim_indicador_mock):
    df_rank_default, _ = ranking_setorial(
        painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock, fato_macro_mock, dim_indicador_mock
    )
    pesos_alt = {"retorno_bolsa": 10.0, "resiliencia_macro": 0.1, "solidez_contabil": 0.1}
    df_rank_alt, _ = ranking_setorial(
        painel_cvm_mock, fato_cotacoes_mock, dim_empresa_mock, fato_macro_mock, dim_indicador_mock, pesos=pesos_alt
    )
    assert not df_rank_alt.empty
    # Scores finais devem diferir devido à alteração drástica dos pesos
    assert not df_rank_default["score_final"].equals(df_rank_alt["score_final"])


def test_entradas_vazias():
    df_aperto, avisos_a = efeito_aperto(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert df_aperto.empty
    assert len(avisos_a) > 0

    df_rank, avisos_r = ranking_setorial(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert df_rank.empty
    assert len(avisos_r) > 0