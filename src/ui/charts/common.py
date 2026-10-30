"""Utilitários de composição de gráficos Plotly (sem streamlit, sem I/O)."""

from datetime import date, datetime
from typing import Literal, Optional, Sequence, Tuple, Union

import pandas as pd
import plotly.graph_objects as go

from src.config import theme
from src.ui.charts.template import FMT_PERCENTUAL, aplicar_template

DataLike = Union[str, date, datetime, pd.Timestamp]
Segmento = Tuple[DataLike, DataLike, str]  # (inicio, fim, rotulo)

_OPACIDADE_BANDA = 0.12


def _iso(valor: DataLike) -> str:
    """Normaliza data para 'YYYY-MM-DD' (aceito por eixos de data do Plotly)."""
    return pd.Timestamp(valor).strftime("%Y-%m-%d")


def figura_vazia(mensagem: str, altura: int = 320) -> go.Figure:
    """Figura sem traços, com mensagem centralizada (estado vazio legível)."""
    cor = theme.COLOR_TOKENS
    fig = go.Figure()
    fig.update_layout(
        height=altura,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=mensagem,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=14, color=cor.text_secondary),
            )
        ],
    )
    return aplicar_template(fig)


def linha_horizontal(fig: go.Figure, y: float, texto: str = "") -> go.Figure:
    """Linha de referência horizontal tracejada, com rótulo opcional."""
    cor = theme.COLOR_TOKENS
    opcoes_rotulo = {}
    if texto:
        opcoes_rotulo = dict(
            annotation_text=texto,
            annotation_position="top left",
            annotation_font=dict(size=11, color=cor.text_secondary),
        )
    fig.add_hline(
        y=y,
        line_dash="dash",
        line_width=1,
        line_color=cor.text_muted,
        **opcoes_rotulo,
    )
    return fig


def bandas_periodo(
    fig: go.Figure,
    segmentos: Sequence[Segmento],
    cores: Optional[Sequence[str]] = None,
) -> go.Figure:
    """Áreas sombreadas por intervalo de datas, com entrada na legenda para cada uma."""
    paleta = list(cores) if cores else list(theme.COLOR_TOKENS.categorical_sequence)
    if not paleta:
        return fig

    rotulos_adicionados = set()
    for i, (inicio, fim, rotulo) in enumerate(segmentos):
        cor = paleta[i % len(paleta)]
        fig.add_vrect(
            x0=_iso(inicio),
            x1=_iso(fim),
            fillcolor=cor,
            opacity=_OPACIDADE_BANDA,
            line_width=0,
            layer="below",
        )
        if rotulo not in rotulos_adicionados:
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker=dict(symbol="square", size=10, color=cor, opacity=0.5),
                    name=rotulo,
                    showlegend=True,
                    hoverinfo="skip",
                )
            )
            rotulos_adicionados.add(rotulo)
    return fig


def anotar_ponto(fig: go.Figure, x: DataLike, y: float, texto: str) -> go.Figure:
    """Anotação com seta apontando para um ponto (x, y)."""
    cor = theme.COLOR_TOKENS
    fig.add_annotation(
        x=x,
        y=y,
        text=texto,
        showarrow=True,
        arrowhead=2,
        arrowsize=1,
        arrowwidth=1,
        arrowcolor=cor.text_muted,
        ax=0,
        ay=-36,
        bgcolor=cor.surface,
        bordercolor=cor.border_strong,
        borderwidth=1,
        borderpad=4,
        font=dict(size=11, color=cor.text_primary),
    )
    return fig


def eixo_percentual(
    fig: go.Figure, eixo: Literal["x", "y"] = "y", casas: Optional[int] = None
) -> go.Figure:
    """Formata um eixo como percentual (valores em fração: 0,1234 -> 12,3%)."""
    formato = FMT_PERCENTUAL if casas is None else f".{casas}%"
    if eixo == "y":
        fig.update_yaxes(tickformat=formato)
    else:
        fig.update_xaxes(tickformat=formato)
    return fig