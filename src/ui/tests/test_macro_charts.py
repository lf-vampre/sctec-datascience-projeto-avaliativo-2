import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from src.ui.charts.macro_charts import (
    fig_dispersao_ptax_ipca,
    fig_heatmap_correlacao,
    fig_ibc,
    fig_politica_monetaria,
    fig_ptax,
)

PALAVRAS_CAUSAIS_PROIBIDAS = ["causou", "provocou", "gerou", "acarretou", "causa"]


def _verificar_texto_nao_causal(fig: go.Figure) -> None:
    """Valida se títulos, eixos e anotações da figura não contêm afirmações causais."""
    textos = []
    if fig.layout.title and fig.layout.title.text:
        textos.append(fig.layout.title.text.lower())
    for ann in fig.layout.annotations or []:
        if ann.text:
            textos.append(ann.text.lower())

    for t in textos:
        for p in PALAVRAS_CAUSAIS_PROIBIDAS:
            assert p not in t, f"Palavra causal '{p}' encontrada no texto: '{t}'"


def test_fig_politica_monetaria_tracos():
    painel = pd.DataFrame(
        {
            "SELIC_META": [13.75, 12.75],
            "IPCA_12M": [5.6, 4.2],
            "JURO_REAL_EXPOST": [8.0, 7.5],
        },
        index=["2023-01", "2023-02"],
    )

    fig = fig_politica_monetaria(painel)
    assert isinstance(fig, go.Figure)
    # 1 barra (juro real) + 2 linhas (selic e ipca)
    assert len(fig.data) == 3
    tipos = [traco.type for traco in fig.data]
    assert "bar" in tipos
    assert tipos.count("scatter") == 2
    _verificar_texto_nao_causal(fig)


def test_fig_politica_monetaria_vazia():
    fig = fig_politica_monetaria(pd.DataFrame())
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_fig_ptax_tracos_e_bandas():
    ptax_d = pd.Series([5.0, 5.2, 5.5, 5.1], index=pd.date_range("2023-01-01", periods=4))
    janelas = pd.DataFrame([{"inicio": "2023-01-02", "fim": "2023-01-03", "dias": 2}])

    fig = fig_ptax(ptax_d, media=5.2, janelas_acima=janelas)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    _verificar_texto_nao_causal(fig)


def test_fig_ptax_vazia():
    fig = fig_ptax(pd.Series(dtype=float))
    assert len(fig.data) == 0


def test_fig_dispersao_ptax_ipca_cor_tamanho():
    painel = pd.DataFrame(
        {
            "PTAX_VENDA": [5.0, 5.2, 5.1, 4.9],
            "IPCA_12M": [5.0, 5.5, 5.2, 4.8],
            "SELIC_META": [10.0, 11.0, 12.0, 13.0],
        },
        index=["2022-01", "2022-02", "2023-01", "2023-02"],
    )

    fig = fig_dispersao_ptax_ipca(painel, defasagem=0)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    # Verifica anotação de correlação r e n
    anns = [a.text for a in fig.layout.annotations if a.text and "r =" in a.text]
    assert len(anns) == 1
    _verificar_texto_nao_causal(fig)


def test_fig_dispersao_vazia():
    fig = fig_dispersao_ptax_ipca(pd.DataFrame())
    assert len(fig.data) == 0


def test_fig_ibc_com_ciclos():
    painel = pd.DataFrame(
        {"IBC_BR_SA": [140.0, 142.0, 141.0]},
        index=["2023-01", "2023-02", "2023-03"],
    )
    ciclos = pd.DataFrame(
        [{"inicio": "2023-01-01", "fim": "2023-02-01", "tipo": "aperto"}]
    )

    fig = fig_ibc(painel, ciclos)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    _verificar_texto_nao_causal(fig)


def test_fig_ibc_vazia():
    fig = fig_ibc(pd.DataFrame())
    assert len(fig.data) == 0


def test_fig_heatmap_correlacao():
    matriz = pd.DataFrame(
        [[1.0, 0.5], [0.5, 1.0]],
        index=["SELIC_META", "IPCA_12M"],
        columns=["SELIC_META", "IPCA_12M"],
    )

    fig = fig_heatmap_correlacao({"matriz": matriz, "n_obs": 20})
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].type == "heatmap"
    _verificar_texto_nao_causal(fig)


def test_fig_heatmap_vazio():
    fig = fig_heatmap_correlacao(pd.DataFrame())
    assert len(fig.data) == 0