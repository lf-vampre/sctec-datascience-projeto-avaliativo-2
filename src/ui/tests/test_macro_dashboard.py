from unittest.mock import patch
import pandas as pd
import pytest

from src.models.contracts import Filtros
from src.ui.dashboards import macro_dashboard
from src.ui.data_loader import Carga, DadosIndisponiveis
from src.ui.prep.macro_story import gerar_storytelling_macro

PALAVRAS_CAUSAIS_PROIBIDAS = ["causou", "provocou", "gerou", "devido a", "causa"]


def test_macro_story_nao_causal_e_dinamico():
    painel = pd.DataFrame(
        {"SELIC_META": [13.75, 12.75], "JURO_REAL_EXPOST": [0.08, 0.07]},
        index=["2023-01", "2023-02"],
    )
    kpis = {"selic_vigente": 12.75, "ipca_12m": 4.5}
    juros_max = pd.DataFrame([{"ano_mes": "2023-01", "JURO_REAL_EXPOST": 0.08}])

    story = gerar_storytelling_macro(painel, kpis, juros_max)

    for chave, texto in story.items():
        texto_lower = texto.lower()
        for p in PALAVRAS_CAUSAIS_PROIBIDAS:
            assert p not in texto_lower, f"Termo causal '{p}' encontrado em {chave}: {texto}"

    assert "12.75% a.a." in story["contexto"]
    assert "2023-01" in story["insight"]


def test_macro_story_dados_vazios():
    story = gerar_storytelling_macro(pd.DataFrame(), {}, pd.DataFrame())
    assert "não disponíveis" in story["contexto"]


@patch("src.ui.dashboards.macro_dashboard.load_gold")
@patch("src.ui.dashboards.macro_dashboard.load_dim")
def test_macro_dashboard_render_dados_indisponiveis(mock_load_dim, mock_load_gold):
    mock_load_gold.side_effect = DadosIndisponiveis("Dados indisponíveis")

    filtros = Filtros(
        periodo=("2019-01-01", "2023-12-31"),
        tickers=("PETR4",),
        setores=("Energia",),
        indicadores_bacen=("SELIC_META",),
    )

    macro_dashboard.render(filtros)
    mock_load_gold.assert_called_once()


@patch("src.ui.dashboards.macro_dashboard.load_gold")
@patch("src.ui.dashboards.macro_dashboard.load_dim")
def test_macro_dashboard_render_sucesso(mock_load_dim, mock_load_gold):
    df_macro = pd.DataFrame([
        {"sk_tempo": 20230101, "sk_indicador": 1, "valor": 13.75, "data": "2023-01-01"},
        {"sk_tempo": 20230101, "sk_indicador": 2, "valor": 5.0, "data": "2023-01-01"},
    ])
    df_dim = pd.DataFrame([
        {"sk_indicador": 1, "codigo": "SELIC_META", "agg_mensal": "ultimo"},
        {"sk_indicador": 2, "codigo": "PTAX_VENDA", "agg_mensal": "media"},
    ])

    mock_load_gold.return_value = Carga(df_macro, "parquet", None)
    mock_load_dim.return_value = Carga(df_dim, "parquet", None)

    filtros = Filtros(
        periodo=("2023-01-01", "2023-12-31"),
        tickers=("PETR4",),
        setores=("Energia",),
        indicadores_bacen=("SELIC_META", "PTAX_VENDA"),
    )

    macro_dashboard.render(filtros)
    mock_load_gold.assert_called_once()
    mock_load_dim.assert_called_once()