"""Testes do template Plotly `fx` e dos utilitários de gráficos."""

from dataclasses import replace
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import pytest
import ast

from src.config import theme
from src.ui.charts import common, template


def _remover_template() -> None:
    if template.NOME_TEMPLATE in pio.templates:
        del pio.templates[template.NOME_TEMPLATE]


@pytest.fixture(autouse=True)
def template_limpo():
    _remover_template()
    yield
    _remover_template()


def _figura_teste() -> go.Figure:
    return go.Figure(go.Scatter(x=["2023-01-01", "2023-02-01"], y=[1.0, 2.0], name="serie"))


# ------------------------------------------------------------------------------
# Template
# ------------------------------------------------------------------------------
def test_registrar_template_cria_fx_com_separadores_pt_br():
    template.registrar_template()
    assert template.NOME_TEMPLATE in pio.templates
    assert pio.templates[template.NOME_TEMPLATE].layout.separators == ",."


def test_registrar_template_e_idempotente():
    template.registrar_template()
    template.registrar_template()
    assert list(pio.templates).count(template.NOME_TEMPLATE) == 1


def test_registrar_template_nao_altera_default_global():
    antes = pio.templates.default
    template.registrar_template()
    assert pio.templates.default == antes


def test_aplicar_template_registra_se_ausente_e_usa_tokens():
    assert template.NOME_TEMPLATE not in pio.templates
    fig = template.aplicar_template(_figura_teste())
    layout = fig.layout.template.layout
    assert template.NOME_TEMPLATE in pio.templates
    assert layout.separators == ",."
    assert tuple(layout.colorway) == tuple(theme.COLOR_TOKENS.categorical_sequence)
    assert layout.font.family == theme.TYPOGRAPHY_TOKENS.font_family
    assert layout.font.color == theme.COLOR_TOKENS.text_primary
    assert layout.legend.orientation == "h"


def test_aplicar_template_nao_altera_os_dados():
    fig = _figura_teste()
    x_antes, y_antes = tuple(fig.data[0].x), tuple(fig.data[0].y)
    template.aplicar_template(fig)
    assert len(fig.data) == 1
    assert tuple(fig.data[0].x) == x_antes
    assert tuple(fig.data[0].y) == y_antes
    assert fig.data[0].name == "serie"


def test_mudar_token_do_tema_altera_o_template(monkeypatch):
    novo = replace(
        theme.COLOR_TOKENS,
        categorical_sequence=["#111111", "#222222"],
        text_primary="#333333",
    )
    monkeypatch.setattr(theme, "COLOR_TOKENS", novo)

    template.registrar_template()
    layout = template.aplicar_template(go.Figure()).layout.template.layout

    assert tuple(layout.colorway) == ("#111111", "#222222")
    assert layout.font.color == "#333333"

    monkeypatch.undo()
    template.registrar_template()  # restaura o template com os tokens reais


def test_escala_sequencial_deriva_dos_tokens():
    layout = template.construir_template().layout
    cores = [c for _, c in layout.colorscale.sequential]
    assert cores == [theme.COLOR_TOKENS.surface_alt, theme.COLOR_TOKENS.secondary, theme.COLOR_TOKENS.primary]


def test_plotly_config_padrao():
    assert template.PLOTLY_CONFIG["displaylogo"] is False
    assert template.PLOTLY_CONFIG["toImageButtonOptions"]["filename"] == "fx_grafico"


@pytest.mark.parametrize("valor, esperado", [("0.875rem", 14), ("1rem", 16), ("12px", 12), ("0.75rem", 12)])
def test_conversao_de_tamanho_para_px(valor, esperado):
    assert template._para_px(valor) == esperado


# ------------------------------------------------------------------------------
# common.py
# ------------------------------------------------------------------------------
def test_figura_vazia_tem_mensagem_e_nenhum_traco():
    fig = common.figura_vazia("Sem dados para o período")
    assert len(fig.data) == 0
    assert [a.text for a in fig.layout.annotations] == ["Sem dados para o período"]
    assert fig.layout.xaxis.visible is False
    assert fig.layout.yaxis.visible is False


def test_bandas_periodo_adiciona_uma_area_e_uma_legenda_por_segmento():
    fig = _figura_teste()
    segmentos = [
        ("2023-01-01", "2023-01-31", "Alta"),
        (pd.Timestamp("2023-02-01"), pd.Timestamp("2023-02-28"), "Estável"),
    ]
    common.bandas_periodo(fig, segmentos)

    assert len(fig.layout.shapes) == 2
    legendas = [t.name for t in fig.data if t.showlegend and t.name in {"Alta", "Estável"}]
    assert legendas == ["Alta", "Estável"]
    assert fig.layout.shapes[0].x0 == "2023-01-01"
    assert fig.layout.shapes[1].x0 == "2023-02-01"


def test_bandas_periodo_usa_cores_informadas_em_ciclo():
    fig = go.Figure()
    segmentos = [("2023-01-01", "2023-01-31", f"s{i}") for i in range(3)]
    common.bandas_periodo(fig, segmentos, cores=["#AAAAAA", "#BBBBBB"])
    assert [s.fillcolor for s in fig.layout.shapes] == ["#AAAAAA", "#BBBBBB", "#AAAAAA"]


def test_bandas_periodo_usa_paleta_do_tema_por_padrao():
    fig = go.Figure()
    common.bandas_periodo(fig, [("2023-01-01", "2023-01-31", "a")])
    assert fig.layout.shapes[0].fillcolor == theme.COLOR_TOKENS.categorical_sequence[0]


def test_bandas_periodo_sem_segmentos_nao_altera_figura():
    fig = _figura_teste()
    common.bandas_periodo(fig, [])
    assert len(fig.layout.shapes) == 0
    assert len(fig.data) == 1


def test_linha_horizontal_tracejada_com_rotulo():
    fig = common.linha_horizontal(_figura_teste(), 100, "Base 100")
    assert len(fig.layout.shapes) == 1
    assert fig.layout.shapes[0].y0 == 100
    assert fig.layout.shapes[0].line.dash == "dash"
    assert [a.text for a in fig.layout.annotations] == ["Base 100"]


def test_linha_horizontal_sem_rotulo_nao_cria_anotacao():
    fig = common.linha_horizontal(_figura_teste(), 0)
    assert len(fig.layout.annotations) == 0


def test_anotar_ponto_cria_anotacao_com_seta():
    fig = common.anotar_ponto(_figura_teste(), "2023-02-01", 2.0, "Pico")
    anotacao = fig.layout.annotations[0]
    assert anotacao.text == "Pico"
    assert anotacao.showarrow is True
    assert anotacao.y == 2.0


def test_eixo_percentual_padrao_e_casas():
    fig = common.eixo_percentual(_figura_teste())
    assert fig.layout.yaxis.tickformat == template.FMT_PERCENTUAL

    fig2 = common.eixo_percentual(_figura_teste(), eixo="x", casas=2)
    assert fig2.layout.xaxis.tickformat == ".2%"


def test_utilitarios_retornam_a_propria_figura():
    fig = _figura_teste()
    assert common.linha_horizontal(fig, 1) is fig
    assert common.anotar_ponto(fig, "2023-01-01", 1.0, "a") is fig
    assert common.eixo_percentual(fig) is fig
    assert common.bandas_periodo(fig, []) is fig


# ------------------------------------------------------------------------------
# Isolamento
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("modulo", [template, common])
def test_modulos_nao_importam_streamlit(modulo):
    arvore = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    assert "streamlit" not in importados