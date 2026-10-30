"""Módulo de construção das figuras Plotly do Dashboard Macro (D1).

Funções puras (DataFrame -> go.Figure) sem streamlit nem I/O.
"""

from typing import Any, Dict, Optional, Union
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.config import theme
from src.ui.charts.common import (
    bandas_periodo,
    figura_vazia,
    linha_horizontal,
)
from src.ui.charts.template import aplicar_template


def fig_politica_monetaria(painel: pd.DataFrame) -> go.Figure:
    """Gráfico combinado de Política Monetária: Selic Meta (linha), IPCA 12M (linha) e Juro Real Ex-Post (barras)."""
    if painel.empty:
        return figura_vazia("Sem dados de política monetária")

    cols_necessarias = ["SELIC_META", "IPCA_12M", "JURO_REAL_EXPOST"]
    if not any(c in painel.columns for c in cols_necessarias):
        return figura_vazia("Indicadores de política monetária ausentes")

    df = painel.copy()
    eixo_x = df.index.astype(str)

    fig = go.Figure()

    # Barras de Juro Real Ex-Post
    if "JURO_REAL_EXPOST" in df.columns and df["JURO_REAL_EXPOST"].notna().any():
        s_jr = df["JURO_REAL_EXPOST"].astype(float)
        # Se os valores do Juro Real estiverem em fração (ex: 0.08), converte para percentual
        if s_jr.abs().max() <= 1.0:
            s_jr = s_jr * 100.0

        fig.add_trace(
            go.Bar(
                x=eixo_x,
                y=s_jr,
                name="Juro Real Ex-Post (% a.a.)",
                marker_color=theme.COLOR_TOKENS.secondary,
                opacity=0.6,
                hovertemplate="<b>%{x}</b><br>Juro Real: %{y:.2f}% a.a.<extra></extra>",
            )
        )

    # Linha da Selic Meta
    if "SELIC_META" in df.columns and df["SELIC_META"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=eixo_x,
                y=df["SELIC_META"],
                mode="lines+markers",
                name="Selic Meta (% a.a.)",
                line=dict(color=theme.COLOR_TOKENS.primary, width=2.5),
                hovertemplate="<b>%{x}</b><br>Selic Meta: %{y:.2f}% a.a.<extra></extra>",
            )
        )

    # Linha do IPCA 12M
    if "IPCA_12M" in df.columns and df["IPCA_12M"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=eixo_x,
                y=df["IPCA_12M"],
                mode="lines",
                name="IPCA 12M (% a.a.)",
                line=dict(color=theme.COLOR_TOKENS.warning, width=2, dash="dash"),
                hovertemplate="<b>%{x}</b><br>IPCA 12M: %{y:.2f}% a.a.<extra></extra>",
            )
        )

    if len(fig.data) == 0:
        return figura_vazia("Dados insuficientes para política monetária")

    fig.update_layout(
        title=dict(text="Política Monetária: Selic Meta, IPCA 12M e Juro Real Ex-Post"),
        xaxis=dict(title=dict(text="Ano-Mês")),
        yaxis=dict(title=dict(text="% a.a.")),
        barmode="relative",
    )

    return aplicar_template(fig)


def fig_ptax(
    diaria_ptax: pd.Series,
    media: Optional[float] = None,
    janelas_acima: Optional[pd.DataFrame] = None,
) -> go.Figure:
    """Gráfico de linha do Dólar PTAX com linha de média do período e áreas sombreadas nas janelas acima da média."""
    clean = diaria_ptax.dropna().sort_index()
    if clean.empty:
        return figura_vazia("Sem dados do Dólar PTAX")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=clean.index.strftime("%Y-%m-%d"),
            y=clean.values,
            mode="lines",
            name="PTAX Venda (R$)",
            line=dict(color=theme.COLOR_TOKENS.primary, width=1.5),
            hovertemplate="<b>%{x}</b><br>PTAX: R$ %{y:.4f}<extra></extra>",
        )
    )

    val_media = media if media is not None else float(clean.mean())
    linha_horizontal(fig, val_media, f"Média (R$ {val_media:.2f})")

    if janelas_acima is not None and not janelas_acima.empty:
        segmentos = []
        for _, row in janelas_acima.iterrows():
            segmentos.append((row["inicio"], row["fim"], "Acima da média"))
        bandas_periodo(fig, segmentos, cores=[theme.COLOR_TOKENS.warning])

    fig.update_layout(
        title=dict(text="Evolução do Dólar PTAX e Períodos Acima da Média"),
        xaxis=dict(title=dict(text="Data")),
        yaxis=dict(title=dict(text="PTAX (R$)")),
    )

    return aplicar_template(fig)


def fig_dispersao_ptax_ipca(
    painel: pd.DataFrame, defasagem: int = 0
) -> go.Figure:
    """Gráfico de dispersão PTAX x IPCA 12M colorido por ano e dimensionado pela Selic Meta."""
    if painel.empty or "PTAX_VENDA" not in painel.columns or "IPCA_12M" not in painel.columns:
        return figura_vazia("Sem dados para dispersão PTAX x IPCA 12M")

    df = painel[["PTAX_VENDA", "IPCA_12M"]].copy()

    if "SELIC_META" in painel.columns:
        df["SELIC_META"] = painel["SELIC_META"]
    else:
        df["SELIC_META"] = 10.0

    if defasagem > 0:
        df["IPCA_12M"] = df["IPCA_12M"].shift(-defasagem)

    df = df.dropna()

    if len(df) < 2:
        return figura_vazia("Dados insuficientes para dispersão PTAX x IPCA 12M")

    dts = pd.to_datetime(df.index, format="%Y-%m", errors="coerce")
    df["Ano"] = dts.year.astype(str)

    r = float(df["PTAX_VENDA"].corr(df["IPCA_12M"]))
    n_obs = len(df)

    fig = px.scatter(
        df,
        x="PTAX_VENDA",
        y="IPCA_12M",
        color="Ano",
        size="SELIC_META",
        size_max=18,
        hover_data={"PTAX_VENDA": ":.2f", "IPCA_12M": ":.2f", "SELIC_META": ":.2f"},
        labels={
            "PTAX_VENDA": "PTAX (R$)",
            "IPCA_12M": "IPCA 12M (% a.a.)",
            "SELIC_META": "Selic Meta (% a.a.)",
            "Ano": "Ano",
        },
    )

    txt_defasagem = f" (IPCA +{defasagem}m)" if defasagem > 0 else ""
    fig.update_layout(
        title=dict(text=f"Dispersão: PTAX x IPCA 12M{txt_defasagem}"),
        xaxis=dict(title=dict(text="PTAX (R$)")),
        yaxis=dict(title=dict(text="IPCA 12M (% a.a.)")),
        annotations=[
            dict(
                text=f"r = {r:.2f} (n = {n_obs})",
                xref="paper",
                yref="paper",
                x=0.98,
                y=0.02,
                xanchor="right",
                yanchor="bottom",
                showarrow=False,
                bgcolor=theme.COLOR_TOKENS.surface,
                bordercolor=theme.COLOR_TOKENS.border_strong,
                borderwidth=1,
                font=dict(size=11, color=theme.COLOR_TOKENS.text_primary),
            )
        ],
    )

    return aplicar_template(fig)


def fig_ibc(
    painel: pd.DataFrame, ciclos: Optional[pd.DataFrame] = None
) -> go.Figure:
    """Gráfico de linha do IBC-Br dessazonalizado com faixas sombreadas por ciclo de Selic."""
    if painel.empty or "IBC_BR_SA" not in painel.columns:
        return figura_vazia("Sem dados de atividade econômica (IBC-Br)")

    s_ibc = painel["IBC_BR_SA"].dropna()
    if s_ibc.empty:
        return figura_vazia("Série do IBC-Br vazia")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=s_ibc.index.astype(str),
            y=s_ibc.values,
            mode="lines+markers",
            name="IBC-Br (com ajuste)",
            line=dict(color=theme.COLOR_TOKENS.primary, width=2),
            hovertemplate="<b>%{x}</b><br>IBC-Br: %{y:.2f}<extra></extra>",
        )
    )

    if ciclos is not None and not ciclos.empty:
        segmentos = []
        mapa_cores = {
            "aperto": theme.COLOR_TOKENS.negative,
            "corte": theme.COLOR_TOKENS.positive,
            "manutencao": theme.COLOR_TOKENS.border_strong,
        }

        for _, row in ciclos.iterrows():
            tipo = row.get("tipo", "manutencao")
            dt_ini = pd.Timestamp(row["inicio"]).strftime("%Y-%m")
            dt_fim = pd.Timestamp(row["fim"]).strftime("%Y-%m")
            segmentos.append((dt_ini, dt_fim, f"Ciclo de {tipo}"))

        bandas_periodo(fig, segmentos)

    fig.update_layout(
        title=dict(text="Atividade Econômica (IBC-Br) e Ciclos de Política Monetária"),
        xaxis=dict(title=dict(text="Ano-Mês")),
        yaxis=dict(title=dict(text="Índice")),
    )

    return aplicar_template(fig)


def fig_heatmap_correlacao(
    corr: Union[Dict[str, Any], pd.DataFrame], n: Optional[int] = None
) -> go.Figure:
    """Heatmap de Correlação de Pearson com anotações numéricas automáticas."""
    if isinstance(corr, dict):
        matriz = corr.get("matriz", pd.DataFrame())
        n_obs = corr.get("n_obs", n)
    else:
        matriz = corr
        n_obs = n

    if matriz is None or matriz.empty:
        return figura_vazia("Sem dados para matriz de correlação")

    z_vals = matriz.values
    cols = list(matriz.columns)

    fig = px.imshow(
        z_vals,
        x=cols,
        y=cols,
        zmin=-1.0,
        zmax=1.0,
        color_continuous_scale="RdBu_r",
        aspect="auto",
        text_auto=".2f",
        labels=dict(color="Pearson (r)"),
    )

    txt_n = f" (n = {n_obs})" if n_obs is not None else ""
    fig.update_layout(
        title=dict(text=f"Matriz de Correlação de Pearson{txt_n}"),
        xaxis=dict(title=dict(text="")),
        yaxis=dict(title=dict(text="")),
    )

    return aplicar_template(fig)