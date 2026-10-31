"""Testes unitários e de renderização de interface para o Dashboard CVM (cvm_dashboard)."""

from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.models.contracts import Filtros
from src.ui.dashboards.cvm_dashboard import render
from src.ui.data_loader import Carga, DadosIndisponiveis
from src.ui.prep.cvm_story import gerar_story_cvm


@pytest.fixture
def mock_filtros() -> Filtros:
    return Filtros(
        periodo=("2019-01-01", "2023-12-31"),
        tickers=("VALE3", "WEGE3", "ITUB4"),
        setores=("Materiais Básicos", "Indústria", "Financeiro"),
        indicadores_bacen=(),
    )


@pytest.fixture
def mock_cargas_completas() -> tuple[Carga, Carga, Carga]:
    df_fato = pd.DataFrame([
        # VALE3 - 2022 / 2023
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 101, "valor": 1000.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 102, "valor": 200.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 104, "valor": 20.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 106, "valor": 15.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 107, "valor": 1.8},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 108, "valor": -50.0},
        {"sk_empresa": 1, "sk_tempo": 20221231, "sk_indicador": 110, "valor": 1000.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 101, "valor": 1200.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 102, "valor": 240.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 104, "valor": 20.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 106, "valor": 18.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 107, "valor": 2.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 108, "valor": 100.0},
        {"sk_empresa": 1, "sk_tempo": 20231231, "sk_indicador": 110, "valor": 1200.0},
        # ITUB4 - 2023
        {"sk_empresa": 3, "sk_tempo": 20231231, "sk_indicador": 102, "valor": 300.0},
        {"sk_empresa": 3, "sk_tempo": 20231231, "sk_indicador": 106, "valor": 20.0},
        {"sk_empresa": 3, "sk_tempo": 20231231, "sk_indicador": 109, "valor": 5000.0},
        {"sk_empresa": 3, "sk_tempo": 20231231, "sk_indicador": 110, "valor": 1500.0},
    ])

    df_emp = pd.DataFrame([
        {
            "sk_empresa": 1,
            "ticker": "VALE3",
            "setor_analitico": "Materiais Básicos",
            "tipo_plano": "industrial",
            "exportadora_commodities": True,
        },
        {
            "sk_empresa": 3,
            "ticker": "ITUB4",
            "setor_analitico": "Financeiro",
            "tipo_plano": "financeira",
            "exportadora_commodities": False,
        },
    ])

    df_ind = pd.DataFrame([
        {"sk_indicador": 101, "codigo": "RECEITA_LIQUIDA"},
        {"sk_indicador": 102, "codigo": "LUCRO_LIQUIDO"},
        {"sk_indicador": 104, "codigo": "MARGEM_LIQUIDA"},
        {"sk_indicador": 106, "codigo": "ROE"},
        {"sk_indicador": 107, "codigo": "LIQUIDEZ_CORRENTE"},
        {"sk_indicador": 108, "codigo": "DIVIDA_LIQUIDA"},
        {"sk_indicador": 109, "codigo": "RECEITA_INTERMEDIACAO"},
        {"sk_indicador": 110, "codigo": "PATRIMONIO_LIQUIDO"},
    ])

    return (
        Carga(df_fato, "parquet", None),
        Carga(df_emp, "parquet", None),
        Carga(df_ind, "parquet", None),
    )


def test_gerar_story_cvm():
    kpis = {
        "ano_foco": 2023,
        "ano_anterior": 2022,
        "receita_liquida_total": 1200.0,
        "receita_delta_pct": 20.0,
        "lucro_liquido_total": 540.0,
        "lucro_delta_pct": 10.0,
        "roe_medio": 19.0,
    }
    crescimento = {
        "empresas": pd.DataFrame([{"ticker": "VALE3", "var_pct": 20.0}]),
        "setores": pd.DataFrame([{"setor_analitico": "Materiais Básicos", "var_pct": 20.0}]),
        "contracoes": [],
    }
    dispersao = {"pontos": pd.DataFrame()}
    solv_df = pd.DataFrame()
    dist_set = {"setores": pd.DataFrame()}

    story = gerar_story_cvm(kpis, crescimento, dispersao, solv_df, dist_set)

    assert "contexto" in story
    assert "insight" in story
    assert "acao" in story
    # Valida RNF-12 (ausência de afirmações causais rígidas)
    assert "causou" not in story["insight"].lower()
    assert "devido a" not in story["insight"].lower()


@patch("src.ui.dashboards.cvm_dashboard.load_gold")
@patch("src.ui.dashboards.cvm_dashboard.load_dim")
def test_render_execucao_sem_excecoes(
    mock_load_dim, mock_load_gold, mock_filtros, mock_cargas_completas
):
    carga_fato, carga_emp, carga_ind = mock_cargas_completas
    mock_load_gold.return_value = carga_fato

    def _dim_side_effect(nome):
        if nome == "dim_empresa":
            return carga_emp
        return carga_ind

    mock_load_dim.side_effect = _dim_side_effect

    try:
        render(mock_filtros)
    except Exception as exc:
        pytest.fail(f"render() lançou exceção inesperada: {exc}")


@patch("src.ui.dashboards.cvm_dashboard.load_gold")
def test_render_dados_indisponiveis(mock_load_gold, mock_filtros):
    mock_load_gold.side_effect = DadosIndisponiveis("Erro simulado")

    try:
        render(mock_filtros)
    except Exception as exc:
        pytest.fail(f"render() lançou exceção ao tratar DadosIndisponiveis: {exc}")