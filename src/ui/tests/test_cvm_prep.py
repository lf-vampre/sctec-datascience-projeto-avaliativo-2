"""Testes unitários para a preparação de dados do Dashboard Fundamentalista CVM (macro_prep / cvm_prep)."""

import numpy as np
import pandas as pd
import pytest

from src.ui.prep.cvm_prep import (
    crescimento_receita,
    dispersao_margem_roe,
    distribuicao_ebit,
    distribuicao_setorial,
    kpis_cvm,
    margens_por_ano,
    painel_anual,
    solvencia,
)


@pytest.fixture
def mock_dimensoes() -> tuple[pd.DataFrame, pd.DataFrame]:
    dim_empresa = pd.DataFrame(
        [
            {
                "sk_empresa": 1,
                "ticker": "VALE3",
                "setor_analitico": "Materiais Básicos",
                "tipo_plano": "industrial",
                "exportadora_commodities": True,
            },
            {
                "sk_empresa": 2,
                "ticker": "WEGE3",
                "setor_analitico": "Indústria",
                "tipo_plano": "industrial",
                "exportadora_commodities": False,
            },
            {
                "sk_empresa": 3,
                "ticker": "ITUB4",
                "setor_analitico": "Financeiro",
                "tipo_plano": "financeira",
                "exportadora_commodities": False,
            },
        ]
    )

    dim_indicador = pd.DataFrame(
        [
            {"sk_indicador": 101, "codigo": "RECEITA_LIQUIDA"},
            {"sk_indicador": 102, "codigo": "LUCRO_LIQUIDO"},
            {"sk_indicador": 103, "codigo": "EBIT"},
            {"sk_indicador": 104, "codigo": "MARGEM_LIQUIDA"},
            {"sk_indicador": 105, "codigo": "MARGEM_EBIT"},
            {"sk_indicador": 106, "codigo": "ROE"},
            {"sk_indicador": 107, "codigo": "LIQUIDEZ_CORRENTE"},
            {"sk_indicador": 108, "codigo": "DIVIDA_LIQUIDA"},
            {"sk_indicador": 109, "codigo": "RECEITA_INTERMEDIACAO"},
            {"sk_indicador": 110, "codigo": "PATRIMONIO_LIQUIDO"},
        ]
    )

    return dim_empresa, dim_indicador


@pytest.fixture
def mock_fato_demonstrativos() -> pd.DataFrame:
    dados = [
        # VALE3 - 2022
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 101, "valor": 1000.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 102, "valor": 200.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 103, "valor": 300.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 104, "valor": 20.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 105, "valor": 30.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 106, "valor": 15.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 107, "valor": 1.8},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 108, "valor": -50.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 110, "valor": 1000.0},
        # VALE3 - 2023
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 101, "valor": 1200.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 102, "valor": 240.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 103, "valor": 360.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 104, "valor": 20.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 105, "valor": 30.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 106, "valor": 18.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 107, "valor": 2.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 108, "valor": 100.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 110, "valor": 1200.0},
        # WEGE3 - 2022
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 101, "valor": 500.0},
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 102, "valor": 50.0},
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 103, "valor": 75.0},
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 104, "valor": 10.0},
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 105, "valor": 15.0},
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 106, "valor": 10.0},
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 107, "valor": 1.2},
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 108, "valor": 150.0},
        {"sk_empresa": 2, "sk_tempo": 20221231, "sk_indicador": 110, "valor": 500.0},
        # WEGE3 - 2023 (Contração de Receita)
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 101, "valor": 450.0},
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 102, "valor": 45.0},
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 103, "valor": 60.0},
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 104, "valor": 10.0},
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 105, "valor": 13.3},
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 106, "valor": 9.0},
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 107, "valor": 1.1},
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 108, "valor": 200.0},
        {"sk_empresa": 2, "sk_tempo": 20231231, "sk_indicador": 110, "valor": 450.0},
        # ITUB4 - 2023 (Financeira)
        {"sk_empresa": 3, "sk_tempo": 20231231, "sk_indicador": 102, "valor": 300.0},
        {"sk_empresa": 3, "sk_tempo": 20231231, "sk_indicador": 106, "valor": 20.0},
        {"sk_empresa": 3, "sk_tempo": 20231231, "sk_indicador": 109, "valor": 5000.0},
        {"sk_empresa": 3, "sk_tempo": 20231231, "sk_indicador": 110, "valor": 1500.0},
    ]
    return pd.DataFrame(dados)


def test_painel_anual(mock_fato_demonstrativos, mock_dimensoes):
    dim_empresa, dim_indicador = mock_dimensoes
    painel, avisos = painel_anual(mock_fato_demonstrativos, dim_empresa, dim_indicador)

    assert not painel.empty
    assert "VALE3" in painel["ticker"].values
    assert "ITUB4" in painel["ticker"].values

    itub_row = painel[(painel["ticker"] == "ITUB4") & (painel["ano"] == 2023)].iloc[0]
    assert not itub_row["comparavel_receita"]
    assert pd.isna(itub_row["RECEITA_LIQUIDA"])
    assert itub_row["RECEITA_INTERMEDIACAO"] == 5000.0
    assert itub_row["LUCRO_LIQUIDO"] == 300.0

    assert any("instituição(ões) financeira(s)" in a for a in avisos)


def test_painel_anual_pl_negativo(mock_dimensoes):
    dim_empresa, dim_indicador = mock_dimensoes
    fato_pl_neg = pd.DataFrame(
        [
            {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 106, "valor": 50.0},
            {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 110, "valor": -100.0},
        ]
    )

    painel, avisos = painel_anual(fato_pl_neg, dim_empresa, dim_indicador)
    val_roe = painel[painel["ticker"] == "VALE3"]["ROE"].iloc[0]

    assert pd.isna(val_roe)
    assert any("PL <= 0 detectado" in a for a in avisos)


def test_kpis_cvm(mock_fato_demonstrativos, mock_dimensoes):
    dim_empresa, dim_indicador = mock_dimensoes
    painel, _ = painel_anual(mock_fato_demonstrativos, dim_empresa, dim_indicador)

    res_2023 = kpis_cvm(painel, 2023)

    # Industriais: VALE3 (1200) + WEGE3 (450) = 1650
    assert res_2023["receita_liquida_total"] == 1650.0
    # LFL Receita 2022 (1500) -> 2023 (1650) = +150
    assert res_2023["receita_delta_anual"] == 150.0

    # Lucro Total: VALE3 (240) + WEGE3 (45) + ITUB4 (300) = 585
    assert res_2023["lucro_liquido_total"] == 585.0
    # LFL Lucro em 2022 era apenas VALE3(200)+WEGE3(50)=250, em 2023 para as mesmas = 285 -> delta +35
    assert res_2023["lucro_delta_anual"] == 35.0

    # ROE Médio: (18 + 9 + 20) / 3 = 15.666...
    assert pytest.approx(res_2023["roe_medio"], 0.01) == 15.67

    # Liquidez Média (só industriais): (2.0 + 1.1) / 2 = 1.55
    assert pytest.approx(res_2023["liquidez_corrente_media"], 0.01) == 1.55


def test_crescimento_receita(mock_fato_demonstrativos, mock_dimensoes):
    dim_empresa, dim_indicador = mock_dimensoes
    painel, _ = painel_anual(mock_fato_demonstrativos, dim_empresa, dim_indicador)

    res = crescimento_receita(painel, 2022, 2023)

    assert "WEGE3" in res["contracoes"]
    assert "VALE3" not in res["contracoes"]
    assert not res["empresas"].empty
    assert not res["setores"].empty


def test_dispersao_margem_roe(mock_fato_demonstrativos, mock_dimensoes):
    dim_empresa, dim_indicador = mock_dimensoes
    painel, _ = painel_anual(mock_fato_demonstrativos, dim_empresa, dim_indicador)

    res = dispersao_margem_roe(painel, 2023)

    assert res["mediana_margem"] is not None
    assert res["mediana_roe"] is not None
    assert "quadrante" in res["pontos"].columns
    assert "ITUB4" not in res["pontos"]["ticker"].values


def test_distribuicao_ebit(mock_fato_demonstrativos, mock_dimensoes):
    dim_empresa, dim_indicador = mock_dimensoes
    painel, _ = painel_anual(mock_fato_demonstrativos, dim_empresa, dim_indicador)

    df_comm = distribuicao_ebit(painel, anos=[2023], agrupamento="commodities")
    assert not df_comm.empty
    assert "Commodities" in df_comm["grupo"].values
    assert "Demais Setores" in df_comm["grupo"].values


def test_solvencia(mock_fato_demonstrativos, mock_dimensoes):
    dim_empresa, dim_indicador = mock_dimensoes
    painel, _ = painel_anual(mock_fato_demonstrativos, dim_empresa, dim_indicador)

    df_solv = solvencia(painel, 2023, limiar_liquidez=1.5)

    wege_row = df_solv[df_solv["ticker"] == "WEGE3"].iloc[0]
    vale_row = df_solv[df_solv["ticker"] == "VALE3"].iloc[0]

    assert wege_row["atencao_liquidez"]  # Liquidez 1.1 < 1.5
    assert not vale_row["atencao_liquidez"]  # Liquidez 2.0 >= 1.5


def test_distribuicao_setorial(mock_fato_demonstrativos, mock_dimensoes):
    dim_empresa, dim_indicador = mock_dimensoes
    painel, _ = painel_anual(mock_fato_demonstrativos, dim_empresa, dim_indicador)

    res = distribuicao_setorial(painel, 2023)

    assert "ITUB4" in res["excluidos_bancos"]
    assert not res["setores"].empty
    assert pytest.approx(res["setores"]["participacao_pct"].sum(), 0.01) == 100.0