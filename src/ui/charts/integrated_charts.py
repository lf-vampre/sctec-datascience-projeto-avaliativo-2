"""Gráficos Plotly para o Dashboard Integrado (D4 - Tríade).

Módulo de funções puras (DataFrame/Series -> go.Figure), sem Streamlit e sem I/O.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import theme
from src.ui.charts.common import aplicar_template, figura_vazia, linha_horizontal
from src.ui.charts.market_charts import fig_base100  # Reuso da Base 100 B3 (STORY-040)


def _aplicar_layout_padrao(fig: go.Figure, titulo: str = "") -> go.Figure:
    """Aplica o template do projeto, título e legenda inferior."""
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


# ------------------------------------------------------------------------------
# Grade Oficial (5 Gráficos da Tríade)
# ------------------------------------------------------------------------------

def fig_macro_cambial(painel_mensal: pd.DataFrame) -> go.Figure:
    """Gráfico multieixo macro-cambial: Selic Meta e IPCA 12M (% a.a.) no eixo 1, PTAX (R$) no eixo 2."""
    if painel_mensal.empty:
        return figura_vazia("Sem dados suficientes para o painel macro-cambial")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    cor = theme.COLOR_TOKENS

    # Eixo 1: Selic Meta (% a.a.)
    if "SELIC_META" in painel_mensal.columns and painel_mensal["SELIC_META"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=painel_mensal.index,
                y=painel_mensal["SELIC_META"],
                mode="lines",
                name="Selic Meta (% a.a.)",
                line=dict(color=cor.primary, width=2.5),
                hovertemplate="<b>Selic Meta:</b> %{y:.2f}% a.a.<br>Mês: %{x}<extra></extra>",
            ),
            secondary_y=False,
        )

    # Eixo 1: IPCA 12M (% a.a.)
    if "IPCA_12M" in painel_mensal.columns and painel_mensal["IPCA_12M"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=painel_mensal.index,
                y=painel_mensal["IPCA_12M"],
                mode="lines",
                name="IPCA 12M (% a.a.)",
                line=dict(color=cor.warning, width=2.0, dash="dash"),
                hovertemplate="<b>IPCA 12M:</b> %{y:.2f}% a.a.<br>Mês: %{x}<extra></extra>",
            ),
            secondary_y=False,
        )

    # Eixo 2: Dólar PTAX (R$)
    if "PTAX_VENDA" in painel_mensal.columns and painel_mensal["PTAX_VENDA"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=painel_mensal.index,
                y=painel_mensal["PTAX_VENDA"],
                mode="lines",
                name="Dólar PTAX (R$)",
                line=dict(color=cor.secondary, width=2.0),
                hovertemplate="<b>Dólar PTAX:</b> R$ %{y:.2f}<br>Mês: %{x}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_xaxes(title_text="Período (Ano-Mês)")
    fig.update_yaxes(title_text="Taxa (% a.a.)", secondary_y=False)
    fig.update_yaxes(title_text="Câmbio (R$)", secondary_y=True)

    return _aplicar_layout_padrao(fig, "Trajetória Conjunta Macro-Cambial (Selic, IPCA e PTAX)")


def fig_barras_contabeis(painel_cvm: pd.DataFrame, ano_foco: int) -> go.Figure:
    """Gráfico de barras contábeis horizontais: Lucro Líquido (R$) e ROE (%) por companhia no exercício de foco."""
    if painel_cvm.empty:
        return figura_vazia("Sem dados suficientes para os demonstrativos contábeis")

    df_curr = painel_cvm[painel_cvm["ano"] == ano_foco].copy()
    if df_curr.empty:
        return figura_vazia(f"Sem dados contábeis para o exercício de {ano_foco}")

    df_curr = df_curr.sort_values("LUCRO_LIQUIDO", ascending=True)

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Lucro Líquido (R$)", "ROE (Return on Equity %)"),
        shared_yaxes=True,
    )
    cor = theme.COLOR_TOKENS

    # Painel 1: Lucro Líquido (R$)
    if "LUCRO_LIQUIDO" in df_curr.columns:
        lucro_m = df_curr["LUCRO_LIQUIDO"] / 1e6
        fig.add_trace(
            go.Bar(
                y=df_curr["ticker"],
                x=lucro_m,
                orientation="h",
                name="Lucro Líquido (R$ Mi)",
                marker_color=cor.primary,
                hovertemplate="<b>%{y}</b><br>Lucro Líquido: R$ %{x:,.2f} Mi<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # Painel 2: ROE (%)
    if "ROE" in df_curr.columns:
        roe_pct = df_curr["ROE"] * 100.0
        fig.add_trace(
            go.Bar(
                y=df_curr["ticker"],
                x=roe_pct,
                orientation="h",
                name="ROE (%)",
                marker_color=cor.secondary,
                hovertemplate="<b>%{y}</b><br>ROE: %{x:.2f}%<extra></extra>",
            ),
            row=1,
            col=2,
        )

    fig.update_xaxes(title_text="R$ Milhões", row=1, col=1)
    fig.update_xaxes(title_text="Percentual (%)", row=1, col=2)
    fig.update_yaxes(title_text="Companhia", row=1, col=1)

    return _aplicar_layout_padrao(fig, f"Lucro Líquido e ROE por Companhia ({ano_foco})")


def fig_setorial_vs_selic(tabela_setorial: pd.DataFrame) -> go.Figure:
    """Barras cruzadas Tríade: Retorno Setorial Anual B3 (%) com Selic Média Anual (% a.a.) no eixo secundário."""
    if tabela_setorial.empty:
        return figura_vazia("Sem dados suficientes para o retorno setorial vs. Selic")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    cor = theme.COLOR_TOKENS
    paleta = cor.categorical_sequence

    setores = sorted(tabela_setorial["setor_analitico"].unique().tolist())
    anos = sorted(tabela_setorial["ano"].unique().tolist())

    for i, setor in enumerate(setores):
        df_set = tabela_setorial[tabela_setorial["setor_analitico"] == setor].sort_values("ano")
        fig.add_trace(
            go.Bar(
                x=df_set["ano"].astype(str),
                y=df_set["retorno_setorial_pct"],
                name=setor,
                marker_color=paleta[i % len(paleta)],
                hovertemplate=f"<b>{setor}</b><br>Ano: %{{x}}<br>Retorno Setorial: %{{y:.2f}}%<extra></extra>",
            ),
            secondary_y=False,
        )

    # Selic Média Anual (% a.a.)
    df_selic = tabela_setorial.groupby("ano")["selic_media_pct"].first().reset_index()
    fig.add_trace(
        go.Scatter(
            x=df_selic["ano"].astype(str),
            y=df_selic["selic_media_pct"],
            mode="lines+markers",
            name="Selic Média Anual (% a.a.)",
            line=dict(color=cor.negative, width=3.0),
            marker=dict(size=8, symbol="diamond"),
            hovertemplate="<b>Selic Média Anual:</b> %{y:.2f}% a.a.<br>Ano: %{x}<extra></extra>",
        ),
        secondary_y=True,
    )

    # Anotação de 1º ano parcial
    parcial_rows = tabela_setorial[tabela_setorial["flag_parcial"]]
    if not parcial_rows.empty:
        ano_parcial = str(parcial_rows.iloc[0]["ano"])
        fig.add_annotation(
            x=ano_parcial,
            y=0,
            text="*1º Ano Parcial",
            showarrow=False,
            font=dict(size=10, color=cor.text_muted),
            yshift=-25,
            secondary_y=False,
        )

    fig.update_xaxes(title_text="Ano Civil")
    fig.update_yaxes(title_text="Retorno Setorial em Bolsa (%)", secondary_y=False)
    fig.update_yaxes(title_text="Selic Média (% a.a.)", secondary_y=True)

    return _aplicar_layout_padrao(fig, "Retorno Setorial em Bolsa vs. Taxa Selic Média Anual")


def fig_dispersao_ebit_retorno(df_dispersao: pd.DataFrame) -> go.Figure:
    """Dispersão fundamentalista: Margem EBIT (%) x Retorno Acumulado em Bolsa (%)."""
    if df_dispersao.empty:
        return figura_vazia("Sem dados suficientes para a dispersão EBIT vs. Retorno em Bolsa")

    df_clean = df_dispersao.dropna(subset=["margem_ebit", "retorno_acumulado_pct"]).copy()
    if df_clean.empty:
        return figura_vazia("Sem observações válidas para Margem EBIT vs. Retorno em Bolsa")

    df_clean["ebit_pct"] = df_clean["margem_ebit"] * 100.0
    rec_max = df_clean["receita_liquida"].max() if "receita_liquida" in df_clean.columns else 1.0
    if pd.isna(rec_max) or rec_max == 0:
        df_clean["size_bubble"] = 14
    else:
        df_clean["size_bubble"] = np.interp(
            df_clean["receita_liquida"].fillna(0),
            [0, rec_max],
            [10, 35],
        )

    df_clean["simbolo_exp"] = df_clean["exportadora_commodities"].map(
        lambda exp: "diamond" if exp else "circle"
    )
    df_clean["tipo_empresa"] = df_clean["exportadora_commodities"].map(
        lambda exp: "Exportadora Commodities" if exp else "Demais Industriais"
    )

    fig = px.scatter(
        df_clean,
        x="ebit_pct",
        y="retorno_acumulado_pct",
        size="size_bubble",
        color="setor_analitico",
        symbol="tipo_empresa",
        text="ticker",
        color_discrete_sequence=theme.COLOR_TOKENS.categorical_sequence,
        labels={
            "ebit_pct": "Margem EBIT (%)",
            "retorno_acumulado_pct": "Retorno Acumulado em Bolsa (%)",
            "setor_analitico": "Setor",
            "tipo_empresa": "Perfil",
        },
    )

    fig.update_traces(
        textposition="top center",
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Margem EBIT: %{x:.2f}%<br>"
            "Retorno em Bolsa: %{y:.2f}%<br>"
            "Receita Líquida: R$ %{customdata[0]}<extra></extra>"
        ),
        customdata=np.stack(
            (
                df_clean["receita_liquida"].map(
                    lambda v: f"{v/1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")
                    if pd.notna(v)
                    else "N/A"
                ),
            ),
            axis=-1,
        ),
    )

    # Linhas de referência nas medianas
    med_ebit = float(df_clean["ebit_pct"].median())
    med_ret = float(df_clean["retorno_acumulado_pct"].median())
    fig.add_vline(x=med_ebit, line_dash="dash", line_color=theme.COLOR_TOKENS.border_strong)
    fig.add_hline(y=med_ret, line_dash="dash", line_color=theme.COLOR_TOKENS.border_strong)

    fig.update_xaxes(title_text="Margem EBIT (%)")
    fig.update_yaxes(title_text="Retorno Acumulado em Bolsa (%)")

    return _aplicar_layout_padrao(fig, "Eficiência Operacional (EBIT %) vs. Desempenho em Bolsa")


# ------------------------------------------------------------------------------
# Perguntas de Negócio (3 Gráficos Complementares)
# ------------------------------------------------------------------------------

def fig_efeito_aperto(tabela_aperto: pd.DataFrame) -> go.Figure:
    """Pergunta 1: Evolução da Despesa Financeira, Lucro Líquido (Base 100) e Alavancagem vs. Selic Média."""
    if tabela_aperto.empty:
        return figura_vazia("Sem dados suficientes para análise do ciclo de aperto")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    cor = theme.COLOR_TOKENS

    anos_str = tabela_aperto["ano"].astype(str)

    # Base 100 Despesa Financeira
    if "despesa_financeira_b100" in tabela_aperto.columns:
        fig.add_trace(
            go.Scatter(
                x=anos_str,
                y=tabela_aperto["despesa_financeira_b100"],
                mode="lines+markers",
                name="Despesa Financeira (Base 100)",
                line=dict(color=cor.negative, width=2.5),
                hovertemplate="<b>Despesa Financeira (Base 100):</b> %{y:.1f}<br>Ano: %{x}<extra></extra>",
            ),
            secondary_y=False,
        )

    # Base 100 Lucro Líquido
    if "lucro_liquido_b100" in tabela_aperto.columns:
        fig.add_trace(
            go.Scatter(
                x=anos_str,
                y=tabela_aperto["lucro_liquido_b100"],
                mode="lines+markers",
                name="Lucro Líquido (Base 100)",
                line=dict(color=cor.primary, width=2.5),
                hovertemplate="<b>Lucro Líquido (Base 100):</b> %{y:.1f}<br>Ano: %{x}<extra></extra>",
            ),
            secondary_y=False,
        )

    # Alavancagem Média (DL/PL)
    if "alavancagem_media" in tabela_aperto.columns:
        fig.add_trace(
            go.Scatter(
                x=anos_str,
                y=tabela_aperto["alavancagem_media"],
                mode="lines+markers",
                name="Alavancagem Média (DL/PL)",
                line=dict(color=cor.warning, width=2.0, dash="dash"),
                hovertemplate="<b>Alavancagem (DL/PL):</b> %{y:.2f}x<br>Ano: %{x}<extra></extra>",
            ),
            secondary_y=True,
        )

    # Selic Média Anual (% a.a.)
    if "selic_media_anual" in tabela_aperto.columns:
        fig.add_trace(
            go.Bar(
                x=anos_str,
                y=tabela_aperto["selic_media_anual"],
                name="Selic Média Anual (% a.a.)",
                marker_color=cor.info,
                opacity=0.6,
                hovertemplate="<b>Selic Média:</b> %{y:.2f}% a.a.<br>Ano: %{x}<extra></extra>",
            ),
            secondary_y=True,
        )

    linha_horizontal(fig, 100.0, texto="Nível Base 100")
    fig.update_xaxes(title_text="Ano Civil")
    fig.update_yaxes(title_text="Índice (Base 100)", secondary_y=False)
    fig.update_yaxes(title_text="Alavancagem (x) / Selic (% a.a.)", secondary_y=True)

    return _aplicar_layout_padrao(fig, "Evolução Contábil durante o Ciclo da Selic")


def fig_exportadoras_estresse(
    df_estresse_ret: pd.DataFrame, df_estresse_margem: pd.DataFrame
) -> go.Figure:
    """Pergunta 3: Retorno em bolsa dentro vs. fora de estresse cambial e Margem EBIT com PTAX."""
    if df_estresse_ret.empty and df_estresse_margem.empty:
        return figura_vazia("Sem dados suficientes para análise de estresse cambial")

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Retorno Diário Médio (Estresse vs. Normalidade)",
            "Margem EBIT Anual vs. PTAX Média",
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": True}]],
    )
    cor = theme.COLOR_TOKENS

    # Painel 1: Retorno Diário Médio dentro vs. fora do estresse
    if not df_estresse_ret.empty:
        grps = df_estresse_ret["grupo"].tolist()
        fig.add_trace(
            go.Bar(
                x=grps,
                y=df_estresse_ret["retorno_diario_medio_dentro_pct"],
                name="Dentro do Estresse Cambial",
                marker_color=cor.negative,
                hovertemplate="<b>%{x} (Estresse):</b> %{y:.3f}% /dia<extra></extra>",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Bar(
                x=grps,
                y=df_estresse_ret["retorno_diario_medio_fora_pct"],
                name="Fora do Estresse Cambial",
                marker_color=cor.secondary,
                hovertemplate="<b>%{x} (Normal):</b> %{y:.3f}% /dia<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # Painel 2: Margem EBIT Exportadoras vs. Demais + PTAX
    if not df_estresse_margem.empty:
        anos_str = df_estresse_margem["ano"].astype(str)
        if "margem_ebit_exportadoras_pct" in df_estresse_margem.columns:
            fig.add_trace(
                go.Scatter(
                    x=anos_str,
                    y=df_estresse_margem["margem_ebit_exportadoras_pct"],
                    mode="lines+markers",
                    name="EBIT Exportadoras (%)",
                    line=dict(color=cor.primary, width=2.5),
                    hovertemplate="<b>Exportadoras EBIT:</b> %{y:.2f}%<br>Ano: %{x}<extra></extra>",
                ),
                row=1,
                col=2,
                secondary_y=False,
            )
        if "margem_ebit_demais_pct" in df_estresse_margem.columns:
            fig.add_trace(
                go.Scatter(
                    x=anos_str,
                    y=df_estresse_margem["margem_ebit_demais_pct"],
                    mode="lines+markers",
                    name="EBIT Demais Industriais (%)",
                    line=dict(color=cor.warning, width=2.0, dash="dash"),
                    hovertemplate="<b>Demais EBIT:</b> %{y:.2f}%<br>Ano: %{x}<extra></extra>",
                ),
                row=1,
                col=2,
                secondary_y=False,
            )
        if "ptax_media_anual" in df_estresse_margem.columns:
            fig.add_trace(
                go.Scatter(
                    x=anos_str,
                    y=df_estresse_margem["ptax_media_anual"],
                    mode="lines",
                    name="PTAX Média (R$)",
                    line=dict(color=cor.text_muted, width=1.5, dash="dot"),
                    hovertemplate="<b>PTAX Média:</b> R$ %{y:.2f}<br>Ano: %{x}<extra></extra>",
                ),
                row=1,
                col=2,
                secondary_y=True,
            )

    fig.update_yaxes(title_text="Retorno Diário (%)", row=1, col=1)
    fig.update_yaxes(title_text="Margem EBIT (%)", row=1, col=2, secondary_y=False)
    fig.update_yaxes(title_text="Dólar PTAX (R$)", row=1, col=2, secondary_y=True)

    return _aplicar_layout_padrao(fig, "Comportamento de Exportadoras em Períodos de Estresse Cambial")


def fig_ranking_setorial(df_ranking: pd.DataFrame) -> go.Figure:
    """Pergunta 4: Ranking setorial com a contribuição empilhada dos 3 pilares à pontuação final."""
    if df_ranking.empty:
        return figura_vazia("Sem dados suficientes para o ranking setorial")

    df_sorted = df_ranking.sort_values("score_final", ascending=True).copy()
    cor = theme.COLOR_TOKENS

    fig = go.Figure()

    # Pilar Bolsa
    fig.add_trace(
        go.Bar(
            y=df_sorted["setor_analitico"],
            x=df_sorted["pilar_bolsa_score"],
            name="Pilar Retorno em Bolsa",
            orientation="h",
            marker_color=cor.primary,
            hovertemplate="<b>%{y}</b><br>Score Bolsa: %{x:.1f} pts<extra></extra>",
        )
    )

    # Pilar Resiliência Macro
    fig.add_trace(
        go.Bar(
            y=df_sorted["setor_analitico"],
            x=df_sorted["pilar_resiliencia_score"],
            name="Pilar Resiliência Macro",
            orientation="h",
            marker_color=cor.secondary,
            hovertemplate="<b>%{y}</b><br>Score Resiliência: %{x:.1f} pts<extra></extra>",
        )
    )

    # Pilar Solidez Contábil
    fig.add_trace(
        go.Bar(
            y=df_sorted["setor_analitico"],
            x=df_sorted["pilar_solidez_score"],
            name="Pilar Solidez Contábil",
            orientation="h",
            marker_color=cor.warning,
            hovertemplate="<b>%{y}</b><br>Score Solidez: %{x:.1f} pts<extra></extra>",
        )
    )

    # Score Final Consolidado (Média Ponderada)
    fig.add_trace(
        go.Bar(
            y=df_sorted["setor_analitico"],
            x=df_sorted["score_final"],
            name="Score Final Consolidado",
            orientation="h",
            marker_color=cor.negative,
            hovertemplate="<b>%{y}</b><br>Score Final Consolidado: %{x:.1f} pts<extra></extra>",
        )
    )

    # Anotação para setores com solidez parcial (Financeiro) posicionada fora da área de barras (x=102)
    for _, row in df_sorted.iterrows():
        if row.get("flag_parcial", False):
            fig.add_annotation(
                y=row["setor_analitico"],
                x=102,
                text="*Solidez Parcial",
                showarrow=False,
                xanchor="left",
                font=dict(size=10, color=cor.text_muted),
            )

    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Pontuação por Pilar (0 - 100)", range=[0, 110], zeroline=True, zerolinecolor=cor.border_strong)
    fig.update_yaxes(title_text="Setor Econômico")

    #return _aplicar_layout_padrao(fig, "Ranking Setorial Multidimensional (Bolsa, Resiliência e Solidez)")
    fig = aplicar_template(fig)
    fig.update_layout(
        title="Ranking Setorial Multidimensional (Bolsa, Resiliência e Solidez)",
        margin=dict(t=60, l=48, r=24, b=80),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.19,
            xanchor="center",
            x=0.5,
        ),
    )
    return fig