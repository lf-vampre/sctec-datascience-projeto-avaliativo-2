"""Testes unitários e de validação de storytelling para o Dashboard Integrado."""

import pandas as pd
import pytest

from src.ui.prep.integrated_story import gerar_story_integrada


@pytest.fixture
def kpis_mock():
    return {
        "selic_vigente": 13.75,
        "selic_delta_12m": 2.0,
        "ipca_12m": 5.79,
        "ipca_delta_12m": -4.0,
        "receita_consolidada": 744380000000.0,
        "receita_delta_pct": 20.0,
        "lucro_consolidado": 122210000000.0,
        "lucro_delta_pct": 10.0,
        "n_empresas_receita": 10,
        "n_empresas_lucro": 12,
    }


@pytest.fixture
def tabela_aperto_mock():
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
def tabela_setorial_mock():
    return pd.DataFrame([
        {
            "ano": 2022,
            "setor_analitico": "Materiais Básicos",
            "retorno_setorial_pct": 15.0,
            "selic_media_pct": 12.38,
            "ipca_12m_dec_pct": 5.79,
            "flag_parcial": False,
        }
    ])


@pytest.fixture
def df_estresse_ret_mock():
    return pd.DataFrame([
        {
            "grupo": "Exportadoras Commodities",
            "retorno_diario_medio_dentro_pct": 0.15,
            "retorno_diario_medio_fora_pct": 0.05,
            "diferenca_pp": 0.10,
        }
    ])


@pytest.fixture
def df_ranking_mock():
    return pd.DataFrame([
        {
            "setor_analitico": "Materiais Básicos",
            "pilar_bolsa_score": 80.0,
            "pilar_resiliencia_score": 75.0,
            "pilar_solidez_score": 85.0,
            "score_final": 80.0,
            "flag_parcial": False,
        }
    ])


def test_integrated_story_ausencia_termos_proibidos(
    kpis_mock, tabela_aperto_mock, tabela_setorial_mock, df_estresse_ret_mock, df_ranking_mock
):
    story = gerar_story_integrada(
        kpis_mock, tabela_aperto_mock, tabela_setorial_mock, df_estresse_ret_mock, df_ranking_mock
    )
    assert "contexto" in story
    assert "insight" in story
    assert "acao" in story

    texto_completo = f"{story['contexto']} {story['insight']} {story['acao']}".lower()
    palavras_proibidas = ["impactou", "afetou", "causou", "provocou", "compre", "venda", "investir"]

    for palavra in palavras_proibidas:
        assert palavra not in texto_completo, f"Termo proibido '{palavra}' encontrado no storytelling."


def test_integrated_story_conteudo_numerico(
    kpis_mock, tabela_aperto_mock, tabela_setorial_mock, df_estresse_ret_mock, df_ranking_mock
):
    story = gerar_story_integrada(
        kpis_mock, tabela_aperto_mock, tabela_setorial_mock, df_estresse_ret_mock, df_ranking_mock
    )
    assert "13.75%" in story["contexto"]
    assert "Materiais Básicos" in story["insight"]
    assert "160.0" in story["insight"]