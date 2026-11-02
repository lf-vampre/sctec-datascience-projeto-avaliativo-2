"""Gráficos Plotly para a seção de Análise Exploratória de Dados (EDA).

Funções puras: DataFrame -> go.Figure. Sem dependência de Streamlit ou I/O.
"""

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import theme
from src.ui.charts.common import aplicar_template, figura_vazia
from src.ui.charts.template import FMT_PERCENTUAL


def fig_nulos_coluna(df_nulos: pd.DataFrame, altura: int = 340) -> go.Figure:
    """Gera gráfico de barras com a porcentagem de nulos por coluna."""
    if df_nulos.empty:
        return figura_vazia("Sem dados de nulos para exibição", altura=altura)

    df_plot = df_nulos.copy()
    if "nulos_pct" not in df_plot.columns:
        return figura_vazia("Coluna 'nulos_pct' não encontrada", altura=altura)

    df_plot = df_plot.sort_values(by="nulos_pct", ascending=True)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_plot["nulos_pct"] / 100.0,
            y=df_plot.index.astype(str),
            orientation="h",
            marker=dict(color=theme.COLOR_TOKENS.primary),
            text=(df_plot["nulos_pct"] / 100.0),
            texttemplate="%{text:.1%}",
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>Nulos: %{text:.1%}<extra></extra>",
        )
    )

    fig.update_layout(
        height=altura,
        title=dict(text="Porcentagem de Valores Nulos por Coluna"),
        xaxis=dict(title="Proporção de Nulos", tickformat=FMT_PERCENTUAL, range=[0, 1.05]),
        yaxis=dict(title="Coluna"),
        showlegend=False,
    )
    return aplicar_template(fig)


def fig_distribuicao_histograma(
    df: pd.DataFrame, coluna: str, altura: int = 380
) -> go.Figure:
    """Gera gráfico de distribuição combinando Histograma e Boxplot marginal em subplots."""
    if df.empty or coluna not in df.columns:
        return figura_vazia(f"Sem dados para a variável '{coluna}'", altura=altura)

    serie = df[coluna].dropna()
    if serie.empty:
        return figura_vazia(f"A variável '{coluna}' possui apenas valores nulos", altura=altura)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.25, 0.75],
        vertical_spacing=0.08,
    )

    # Subplot 1: Boxplot
    fig.add_trace(
        go.Box(
            x=serie,
            name=coluna,
            marker=dict(color=theme.COLOR_TOKENS.secondary),
            boxmean=True,
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # Subplot 2: Histograma
    fig.add_trace(
        go.Histogram(
            x=serie,
            name=coluna,
            marker=dict(color=theme.COLOR_TOKENS.primary),
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        height=altura,
        title=dict(text=f"Distribuição e Outliers — {coluna}"),
        xaxis2=dict(title=coluna),
        yaxis2=dict(title="Frequência"),
    )
    return aplicar_template(fig)


def fig_cobertura_temporal(
    df: pd.DataFrame,
    col_grupo: str,
    col_data: str,
    altura: int = 360,
) -> go.Figure:
    """Gera visualização da cobertura de observações no tempo por entidade/grupo."""
    if df.empty or col_grupo not in df.columns or col_data not in df.columns:
        return figura_vazia("Sem dados de cobertura temporal para exibição", altura=altura)

    df_plot = df[[col_grupo, col_data]].dropna().copy()
    if df_plot.empty:
        return figura_vazia("Sem datas válidas para cobertura temporal", altura=altura)

    df_plot[col_data] = pd.to_datetime(df_plot[col_data])
    agrupado = (
        df_plot.groupby([col_grupo, pd.Grouper(key=col_data, freq="ME")])
        .size()
        .reset_index(name="obs_qtd")
    )

    fig = go.Figure()
    for grupo, grp in agrupado.groupby(col_grupo):
        fig.add_trace(
            go.Scatter(
                x=grp[col_data],
                y=grp["obs_qtd"],
                mode="lines+markers",
                name=str(grupo),
                hovertemplate=f"<b>{grupo}</b><br>Data: %{{x|%Y-%m}}<br>Obs: %{{y}}<extra></extra>",
            )
        )

    fig.update_layout(
        height=altura,
        title=dict(text=f"Cobertura Temporal Mensal por {col_grupo.replace('_', ' ').capitalize()}"),
        xaxis=dict(title="Período"),
        yaxis=dict(title="Quantidade de Observações"),
        legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.25,
                    xanchor="center",
                    x=0.5,
                ),
    )
    return aplicar_template(fig)


def fig_assimetria_curtose(df_metricas: pd.DataFrame, altura: int = 360) -> go.Figure:
    """Gera gráfico de barras comparativo de Assimetria e Curtose (para cotações B3)."""
    if df_metricas.empty or "ticker" not in df_metricas.columns:
        return figura_vazia("Sem métricas de assimetria e curtose disponíveis", altura=altura)

    cols_req = {"assimetria", "curtose"}
    if not cols_req.issubset(df_metricas.columns):
        return figura_vazia("Colunas 'assimetria' ou 'curtose' ausentes no DataFrame", altura=altura)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_metricas["ticker"],
            y=df_metricas["assimetria"],
            name="Assimetria (Skewness)",
            marker=dict(color=theme.COLOR_TOKENS.primary),
        )
    )
    fig.add_trace(
        go.Bar(
            x=df_metricas["ticker"],
            y=df_metricas["curtose"],
            name="Curtose (Excesso)",
            marker=dict(color=theme.COLOR_TOKENS.secondary),
        )
    )

    fig.update_layout(
        height=altura,
        title=dict(text="Diagnóstico Estatístico: Assimetria e Excesso de Curtose"),
        xaxis=dict(title="Ticker"),
        yaxis=dict(title="Valor Estatístico"),
        barmode="group",
        legend=dict(
                            orientation="h",
                            yanchor="top",
                            y=-0.25,
                            xanchor="center",
                            x=0.5,
                        ),
    )
    return aplicar_template(fig)