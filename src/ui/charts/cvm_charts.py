"""Gráficos Plotly para o Dashboard Fundamentalista CVM (D2)."""

from typing import Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import theme
from src.ui.charts.common import aplicar_template, figura_vazia, linha_horizontal
from src.utils.formatting import format_currency, format_number, format_percent


def _formatar_bilhoes_ou_milhoes(val: float) -> str:
    """Formata valores numéricos para R$ bilhões ou R$ milhões em rótulos/hovers."""
    if pd.isna(val):
        return "N/A"
    abs_val = abs(val)
    if abs_val >= 1e9:
        return f"R$ {val / 1e9:,.2f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs_val >= 1e6:
        return f"R$ {val / 1e6:,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
    return format_currency(val)


def _aplicar_layout_padrao(fig: go.Figure, titulo: str = "") -> go.Figure:
    """Aplica o template do projeto, título e posição de legenda padronizada (centralizada na parte inferior)."""
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


def fig_receita_agrupada(painel: pd.DataFrame) -> Tuple[go.Figure, Optional[go.Figure]]:
    """Gera dois gráficos independentes de barras agrupadas: Industriais e Financeiras (ADR-09)."""
    if painel.empty:
        return figura_vazia("Sem dados para exibição da Receita Líquida"), None

    df = painel.copy()
    has_ind = (df["comparavel_receita"] & df["RECEITA_LIQUIDA"].notna()).any()
    has_fin = (~df["comparavel_receita"] & df["RECEITA_INTERMEDIACAO"].notna()).any()

    if not has_ind and not has_fin:
        return figura_vazia("Sem dados de receita para o filtro selecionado"), None

    fig_ind, fig_fin = None, None

    if has_ind:
        sub_ind = df[df["comparavel_receita"] & df["RECEITA_LIQUIDA"].notna()].copy()
        sub_ind["ano_str"] = sub_ind["ano"].astype(str)
        sub_ind["receita_fmt"] = sub_ind["RECEITA_LIQUIDA"].apply(_formatar_bilhoes_ou_milhoes)
        fig_ind = px.bar(
            sub_ind,
            x="ticker",
            y="RECEITA_LIQUIDA",
            color="ano_str",
            barmode="group",
            custom_data=["receita_fmt"],
            title="Receita Líquida (Industriais / Comerciais)",
            labels={"ticker": "Empresa", "RECEITA_LIQUIDA": "Receita Líquida (R$)", "ano_str": "Ano"},
        )
        fig_ind.update_traces(
            hovertemplate="<b>%{x}</b> (%{fullData.name})<br>Receita Líquida: %{customdata[0]}<extra></extra>"
        )
        fig_ind = _aplicar_layout_padrao(fig_ind, "Receita Líquida — Industriais / Comerciais")

    if has_fin:
        sub_fin = df[~df["comparavel_receita"] & df["RECEITA_INTERMEDIACAO"].notna()].copy()
        sub_fin["ano_str"] = sub_fin["ano"].astype(str)
        sub_fin["receita_fmt"] = sub_fin["RECEITA_INTERMEDIACAO"].apply(_formatar_bilhoes_ou_milhoes)
        fig_fin = px.bar(
            sub_fin,
            x="ticker",
            y="RECEITA_INTERMEDIACAO",
            color="ano_str",
            barmode="group",
            custom_data=["receita_fmt"],
            title="Receita de Intermediação Financeira (Instituições Financeiras)",
            labels={"ticker": "Empresa", "RECEITA_INTERMEDIACAO": "Receita Intermediação (R$)", "ano_str": "Ano"},
        )
        fig_fin.update_traces(
            hovertemplate="<b>%{x}</b> (%{fullData.name})<br>Receita Intermediação: %{customdata[0]}<extra></extra>"
        )
        fig_fin = _aplicar_layout_padrao(fig_fin, "Receita Intermediação — Financeiras (Não Comparável)")

    if fig_ind is None:
        return fig_fin, None

    return fig_ind, fig_fin


def fig_donut_setorial(dist_setorial: Dict) -> go.Figure:
    """Gráfico de Rosca (Donut) da participação da Receita Líquida por Setor."""
    df_setores = dist_setorial.get("setores", pd.DataFrame())
    if df_setores.empty or "setor_analitico" not in df_setores.columns:
        return figura_vazia("Sem dados setoriais de receita para o exercício foco")

    fig = px.pie(
        df_setores,
        names="setor_analitico",
        values="RECEITA_LIQUIDA",
        hole=0.4,
        title="Distribuição Setorial da Receita Líquida (Exclui Financeiras)",
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Receita: %{customdata}<br>Participação: %{percent}<extra></extra>",
        customdata=[_formatar_bilhoes_ou_milhoes(v) for v in df_setores["RECEITA_LIQUIDA"]],
    )
    return _aplicar_layout_padrao(fig, "Distribuição Setorial da Receita Líquida")


def fig_margem_roe(dispersao: Dict, medianas: Optional[Tuple[float, float]] = None) -> go.Figure:
    """Dispersão em quadrantes: Margem Líquida (X) x ROE (Y) com tamanho por Receita."""
    df_pontos = dispersao.get("pontos", pd.DataFrame())

    if df_pontos.empty:
        return figura_vazia("Sem dados válidos de Margem Líquida e ROE")

    med_m = dispersao.get("mediana_margem") if medianas is None else medianas[0]
    med_r = dispersao.get("mediana_roe") if medianas is None else medianas[1]

    # Preenche receitas nulas/negativas com valor simbólico para tamanho de bolha
    df_plot = df_pontos.copy()
    rec_base = df_plot["RECEITA_LIQUIDA"].fillna(1.0).clip(lower=1.0)
    df_plot["tamanho_bolha"] = np.sqrt(rec_base)

    fig = px.scatter(
        df_plot,
        x="MARGEM_LIQUIDA",
        y="ROE",
        size="tamanho_bolha",
        color="quadrante",
        text="ticker",
        title="Dispersão: Margem Líquida vs. ROE (Tamanho = Receita Líquida)",
        labels={"MARGEM_LIQUIDA": "Margem Líquida (%)", "ROE": "ROE (%)", "quadrante": "Quadrante"},
    )

    fig.update_traces(
        textposition="top center",
        hovertemplate="<b>%{text}</b><br>Margem Líquida: %{x:.2f}%<br>ROE: %{y:.2f}%<br>Quadrante: %{fullData.name}<extra></extra>",
    )

    if med_m is not None:
        fig.add_vline(x=med_m, line_dash="dash", line_color=theme.COLOR_TOKENS.text_muted)
    if med_r is not None:
        fig.add_hline(y=med_r, line_dash="dash", line_color=theme.COLOR_TOKENS.text_muted)

    return _aplicar_layout_padrao(fig, "Matriz Margem Líquida vs. ROE por Companhia")


def fig_boxplot_ebit(distribuicao: pd.DataFrame) -> go.Figure:
    """Boxplot da Margem EBIT com subplots dinâmicos por Grupo/Setor (escalas Y independentes)."""
    if distribuicao.empty or "grupo" not in distribuicao.columns:
        return figura_vazia("Sem dados suficientes de Margem EBIT para a distribuição")

    df_plot = distribuicao.dropna(subset=["MARGEM_EBIT"]).copy()
    if df_plot.empty:
        return figura_vazia("Sem observações válidas de Margem EBIT")

    grupos = sorted(df_plot["grupo"].unique())
    n_grupos = len(grupos)

    titulos_subplots = [
        f"{g} (n={len(df_plot[df_plot['grupo'] == g])})" for g in grupos
    ]

    fig = make_subplots(
        rows=1,
        cols=n_grupos,
        subplot_titles=titulos_subplots,
        shared_yaxes=False,
    )

    paleta = theme.COLOR_TOKENS.categorical_sequence

    for i, g in enumerate(grupos):
        sub = df_plot[df_plot["grupo"] == g]
        cor = paleta[i % len(paleta)]

        fig.add_trace(
            go.Box(
                y=sub["MARGEM_EBIT"],
                name=g,
                boxpoints="all",
                jitter=0.3,
                pointpos=-1.8,
                marker=dict(color=cor),
                line=dict(color=cor),
                customdata=sub["ticker"],
                hovertemplate="<b>%{customdata}</b><br>Margem EBIT: %{y:.2f}%<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=i + 1,
        )
        fig.update_yaxes(title_text="Margem EBIT (%)", row=1, col=i + 1)

    return _aplicar_layout_padrao(fig, "Distribuição da Margem EBIT por Grupo")


def fig_solvencia(solvencia_df: pd.DataFrame, limiar_liquidez: float = 1.5) -> go.Figure:
    """Barras de Dívida Líquida (eixo esquerdo) com Marcadores de Liquidez Corrente (eixo direito)."""
    if solvencia_df.empty:
        return figura_vazia("Sem dados de solvência para exibição")

    df = solvencia_df.copy()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Cores de atenção para Dívida Líquida / Liquidez
    cores_div = [
        theme.COLOR_TOKENS.negative if row["atencao_liquidez"] else theme.COLOR_TOKENS.primary
        for _, row in df.iterrows()
    ]

    fig.add_trace(
        go.Bar(
            x=df["ticker"],
            y=df["DIVIDA_LIQUIDA"],
            name="Dívida Líquida (R$)",
            marker_color=cores_div,
            hovertemplate="<b>%{x}</b><br>Dívida Líquida: %{customdata}<extra></extra>",
            customdata=[_formatar_bilhoes_ou_milhoes(v) for v in df["DIVIDA_LIQUIDA"]],
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=df["ticker"],
            y=df["LIQUIDEZ_CORRENTE"],
            name="Liquidez Corrente (x)",
            mode="markers+lines",
            marker=dict(size=10, symbol="diamond", color=theme.COLOR_TOKENS.secondary),
            hovertemplate="<b>%{x}</b><br>Liquidez Corrente: %{y:.2f}x<extra></extra>",
        ),
        secondary_y=True,
    )

    # Linha de referência no limiar (1.5x)
    fig.add_hline(
        y=limiar_liquidez,
        line_dash="dash",
        line_color=theme.COLOR_TOKENS.warning,
        annotation_text=f"Limiar ({limiar_liquidez:.1f}x)",
        annotation_position="top right",
        secondary_y=True,
    )

    fig.update_xaxes(title_text="Empresa")
    fig.update_yaxes(title_text="Dívida Líquida (R$)", secondary_y=False)
    fig.update_yaxes(title_text="Liquidez Corrente (x)", secondary_y=True)

    return _aplicar_layout_padrao(fig, "Níveis de Solvência e Liquidez Corrente")


def fig_margem_evolucao(margens: pd.DataFrame) -> go.Figure:
    """Evolução da Margem Líquida ao longo dos exercícios por empresa."""
    if margens.empty:
        return figura_vazia("Sem dados de evolução da Margem Líquida")

    df = margens.copy()
    df["ano_str"] = df["ano"].astype(str)

    fig = px.line(
        df,
        x="ano_str",
        y="MARGEM_LIQUIDA",
        color="ticker",
        markers=True,
        title="Evolução da Margem Líquida por Exercício",
        labels={"ano_str": "Exercício", "MARGEM_LIQUIDA": "Margem Líquida (%)", "ticker": "Empresa"},
    )

    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b> (%{x})<br>Margem Líquida: %{y:.2f}%<extra></extra>"
    )

    return _aplicar_layout_padrao(fig, "Evolução Temporal da Margem Líquida")