"""Gráficos Plotly para o Dashboard de Mercado e Risco B3 (D3).

Módulo de funções puras (DataFrame/Series -> go.Figure), sem Streamlit e sem I/O.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.config import theme
from src.ui.charts.common import aplicar_template, figura_vazia, linha_horizontal


def _aplicar_layout_padrao(fig: go.Figure, titulo: str = "") -> go.Figure:
    """Aplica o template do projeto, título e legenda centralizada na parte inferior."""
    fig = aplicar_template(fig)
    fig.update_layout(
        title=titulo,
        margin=dict(t=60, l=48, r=24, b=80),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
        ),
    )
    return fig


def fig_base100(
    base100_df: pd.DataFrame, destacar: Optional[str] = None
) -> go.Figure:
    """Gráfico de linhas comparativo Base 100 com referência no nível 100."""
    if base100_df.empty:
        return figura_vazia("Sem dados suficientes para exibição da Base 100")

    fig = go.Figure()
    paleta = theme.COLOR_TOKENS.categorical_sequence
    colunas = [c for c in base100_df.columns if c != "Carteira"]

    for i, col in enumerate(colunas):
        opacidade = 1.0 if (destacar is None or destacar == col) else 0.2
        largura = 2.5 if destacar == col else 1.5
        cor = paleta[i % len(paleta)]

        fig.add_trace(
            go.Scatter(
                x=base100_df.index,
                y=base100_df[col],
                mode="lines",
                name=col,
                opacity=opacidade,
                line=dict(width=largura, color=cor),
                hovertemplate=f"<b>{col}</b><br>Data: %{{x|%d/%m/%Y}}<br>Base 100: %{{y:.2f}}<extra></extra>",
            )
        )

    # Carteira equiponderada com traço espesso e cor destacada
    if "Carteira" in base100_df.columns:
        fig.add_trace(
            go.Scatter(
                x=base100_df.index,
                y=base100_df["Carteira"],
                mode="lines",
                name="Carteira Equiponderada",
                line=dict(width=3.5, color=theme.COLOR_TOKENS.primary, dash="dash"),
                hovertemplate="<b>Carteira Equiponderada</b><br>Data: %{x|%d/%m/%Y}<br>Base 100: %{y:.2f}<extra></extra>",
            )
        )

    fig = linha_horizontal(fig, 100.0, texto="Nível Base 100")
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Desempenho (Base 100)")

    return _aplicar_layout_padrao(
        fig, "Rentabilidade Comparativa Normalizada (Base 100)"
    )


def fig_risco_retorno(tabela_rr: pd.DataFrame) -> go.Figure:
    """Gráfico de dispersão Volatilidade vs Retorno Acumulado com bolhas por volume."""
    if tabela_rr.empty:
        return figura_vazia("Sem dados suficientes para o gráfico Risco vs Retorno")

    df_plot = tabela_rr.dropna(subset=["volatilidade_anualizada", "retorno_acumulado"]).copy()
    if df_plot.empty:
        return figura_vazia("Sem dados válidos para a relação Risco vs Retorno")

    df_plot["vol_pct"] = df_plot["volatilidade_anualizada"] * 100.0
    df_plot["ret_pct"] = df_plot["retorno_acumulado"] * 100.0

    # Normalização segura do tamanho da bolha pelo volume diário
    vol_max = df_plot["volume_medio_diario"].max()
    if pd.isna(vol_max) or vol_max == 0:
        df_plot["size_bubble"] = 12
    else:
        df_plot["size_bubble"] = np.interp(
            df_plot["volume_medio_diario"].fillna(0),
            [0, vol_max],
            [10, 35],
        )

    med_vol = float(df_plot["vol_pct"].median())
    med_ret = float(df_plot["ret_pct"].median())

    fig = px.scatter(
        df_plot,
        x="vol_pct",
        y="ret_pct",
        size="size_bubble",
        text="ticker",
        color="ticker",
        color_discrete_sequence=theme.COLOR_TOKENS.categorical_sequence,
        labels={
            "vol_pct": "Volatilidade Anualizada (% a.a.)",
            "ret_pct": "Retorno Acumulado (%)",
            "ticker": "Ativo",
        },
    )

    fig.update_traces(
        textposition="top center",
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Volatilidade: %{x:.2f}% a.a.<br>"
            "Retorno Acumulado: %{y:.2f}%<br>"
            "Índice Sharpe: %{customdata[0]:.2f}<br>"
            "Drawdown Máximo: %{customdata[1]:.2f}%<br>"
            "Vol. Médio Diário: R$ %{customdata[2]}<extra></extra>"
        ),
        customdata=np.stack(
            (
                df_plot["sharpe"].fillna(0),
                df_plot["drawdown_maximo"].fillna(0) * 100.0,
                df_plot["volume_medio_diario"].map(
                    lambda v: f"{v/1e6:,.2f} M".replace(",", "X").replace(".", ",").replace("X", ".")
                    if pd.notna(v)
                    else "N/A"
                ),
            ),
            axis=-1,
        ),
    )

    # Linhas de referência nas medianas
    fig.add_vline(x=med_vol, line_dash="dash", line_color=theme.COLOR_TOKENS.border_strong)
    fig.add_hline(y=med_ret, line_dash="dash", line_color=theme.COLOR_TOKENS.border_strong)

    return _aplicar_layout_padrao(fig, "Relação Risco vs. Retorno (Sharpe & Liquidez)")


def fig_hist_retornos(
    retornos_diarios: pd.Series,
    estatisticas: Dict[str, float],
    titulo_ativo: str = "Carteira",
) -> go.Figure:
    """Histograma da frequência de retornos diários com boxplot marginal e estatísticas de forma."""
    clean_ret = retornos_diarios.dropna()
    if clean_ret.empty:
        return figura_vazia("Sem dados suficientes de retornos diários")

    df_hist = pd.DataFrame({"retorno_pct": clean_ret * 100.0})

    fig = px.histogram(
        df_hist,
        x="retorno_pct",
        marginal="box",
        nbins=40,
        color_discrete_sequence=[theme.COLOR_TOKENS.secondary],
        labels={"retorno_pct": "Retorno Diário (%)"},
    )

    p5 = estatisticas.get("p5", np.nan)
    if not np.isnan(p5):
        p5_pct = p5 * 100.0
        fig.add_vline(
            x=p5_pct,
            line_dash="dot",
            line_color=theme.COLOR_TOKENS.negative,
            annotation_text=f"P5 (Cauda): {p5_pct:.2f}%",
            annotation_position="top left",
        )

    fig.update_traces(
        hovertemplate="Intervalo: %{x:.2f}%<br>Frequência: %{y}<extra></extra>"
    )
    fig.update_xaxes(title_text="Retorno Diário (%)")
    fig.update_yaxes(title_text="Frequência (Dias)")

    return _aplicar_layout_padrao(
        fig, f"Distribuição dos Retornos Diários — {titulo_ativo}"
    )


def fig_drawdown(
    df_drawdown: pd.DataFrame, selecionados: Optional[List[str]] = None
) -> go.Figure:
    """Gráfico de área / linha do drawdown acumulado ao longo do tempo."""
    if df_drawdown.empty:
        return figura_vazia("Sem dados suficientes para exibição do Drawdown")

    fig = go.Figure()
    paleta = theme.COLOR_TOKENS.categorical_sequence

    colunas = (
        [c for c in selecionados if c in df_drawdown.columns]
        if selecionados
        else list(df_drawdown.columns)
    )

    if not colunas and "Carteira" in df_drawdown.columns:
        colunas = ["Carteira"]

    for i, col in enumerate(colunas):
        serie_pct = df_drawdown[col] * 100.0
        cor = (
            theme.COLOR_TOKENS.primary
            if col == "Carteira"
            else paleta[i % len(paleta)]
        )

        fig.add_trace(
            go.Scatter(
                x=df_drawdown.index,
                y=serie_pct,
                mode="lines",
                name=col,
                fill="tozeroy" if len(colunas) == 1 else None,
                line=dict(
                    width=2.5 if col == "Carteira" else 1.5,
                    color=cor,
                    dash="dash" if col == "Carteira" else "solid",
                ),
                hovertemplate=f"<b>{col}</b><br>Data: %{{x|%d/%m/%Y}}<br>Drawdown: %{{y:.2f}}%<extra></extra>",
            )
        )

    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Drawdown (%)", ticksuffix="%")

    return _aplicar_layout_padrao(fig, "Evolução do Drawdown no Tempo")


def fig_sma(df_sma: pd.DataFrame, ticker: str = "") -> go.Figure:
    """Gráfico multilinha de preço de fechamento com sobreposição de SMA 21 e SMA 50."""
    if df_sma.empty or "close" not in df_sma.columns:
        return figura_vazia("Sem dados de cotações/médias móveis para o ativo selecionado")

    fig = go.Figure()

    # Preço de Fechamento
    fig.add_trace(
        go.Scatter(
            x=df_sma.index,
            y=df_sma["close"],
            mode="lines",
            name="Fechamento",
            line=dict(color=theme.COLOR_TOKENS.primary, width=2.0),
            hovertemplate="<b>Fechamento</b><br>Data: %{x|%d/%m/%Y}<br>Preço: R$ %{y:.2f}<extra></extra>",
        )
    )

    # SMA 21 (Curto Prazo)
    if "sma_21" in df_sma.columns and df_sma["sma_21"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df_sma.index,
                y=df_sma["sma_21"],
                mode="lines",
                name="SMA 21 (Curto Prazo)",
                line=dict(color=theme.COLOR_TOKENS.secondary, width=1.5),
                hovertemplate="<b>SMA 21</b><br>Data: %{x|%d/%m/%Y}<br>Preço: R$ %{y:.2f}<extra></extra>",
            )
        )

    # SMA 50 (Médio Prazo)
    if "sma_50" in df_sma.columns and df_sma["sma_50"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df_sma.index,
                y=df_sma["sma_50"],
                mode="lines",
                name="SMA 50 (Médio Prazo)",
                line=dict(color=theme.COLOR_TOKENS.warning, width=1.5),
                hovertemplate="<b>SMA 50</b><br>Data: %{x|%d/%m/%Y}<br>Preço: R$ %{y:.2f}<extra></extra>",
            )
        )

    # Cruzamentos descritivos
    if "cruzamento" in df_sma.columns:
        cruzamentos = df_sma[df_sma["cruzamento"] != "Neutro"]
        for idx, row in cruzamentos.iterrows():
            fig.add_trace(
                go.Scatter(
                    x=[idx],
                    y=[row["close"]],
                    mode="markers",
                    name=row["cruzamento"],
                    marker=dict(
                        size=10,
                        symbol="circle",
                        color=theme.COLOR_TOKENS.info,
                    ),
                    showlegend=False,
                    hovertemplate=f"<b>Evento:</b> {row['cruzamento']}<br>Data: %{{x|%d/%m/%Y}}<extra></extra>",
                )
            )

    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Preço (R$)")

    titulo = f"Preço vs. Médias Móveis (SMA 21 / 50) — {ticker}" if ticker else "Preço vs. Médias Móveis (SMA 21 / 50)"
    return _aplicar_layout_padrao(fig, titulo)