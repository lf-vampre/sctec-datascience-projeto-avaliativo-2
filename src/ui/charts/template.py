"""Template Plotly `fx` gerado dos tokens de design (config/theme.py).

Sem streamlit nem I/O. Mudar cores/fontes em theme.py altera os gráficos sem tocar neste módulo.
"""

from typing import Any, Dict

import plotly.graph_objects as go
import plotly.io as pio

from src.config import theme

NOME_TEMPLATE = "fx"

# Separadores pt-BR: decimal "," e milhar "."
SEPARADORES_PT_BR = ",."

# Formatos d3; com os separadores acima saem em pt-BR (ex.: 1.234,56)
FMT_NUMERO = ",.2f"
FMT_INTEIRO = ",.0f"
FMT_PERCENTUAL = ".1%"  # valor em fração: 0.1234 -> 12,3%

PLOTLY_CONFIG: Dict[str, Any] = {
    "displaylogo": False,
    "displayModeBar": "hover",
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
        "toggleSpikelines",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
    ],
    "toImageButtonOptions": {"format": "png", "filename": "fx_grafico", "scale": 2},
    "locale": "pt-BR",
}


def _para_px(valor: str) -> int:
    """Converte tamanho de token ('0.875rem' ou '14px') para pixels inteiros (base 16px)."""
    if valor.endswith("rem"):
        return round(float(valor.removesuffix("rem")) * 16)
    return round(float(valor.removesuffix("px")))


def construir_template() -> go.layout.Template:
    """Monta o template a partir dos tokens vigentes de config/theme.py."""
    cor = theme.COLOR_TOKENS
    tipo = theme.TYPOGRAPHY_TOKENS

    tam_base = _para_px(tipo.size_sm)
    tam_pequeno = _para_px(tipo.size_xs)
    tam_titulo = _para_px(tipo.size_lg)

    fonte_eixo = dict(size=tam_pequeno, color=cor.text_secondary)

    layout = go.Layout(
        font=dict(family=tipo.font_family, size=tam_base, color=cor.text_primary),
        colorway=list(cor.categorical_sequence),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        separators=SEPARADORES_PT_BR,
        margin=dict(l=48, r=24, t=48, b=48),
        title=dict(x=0, xanchor="left", font=dict(size=tam_titulo, color=cor.text_primary)),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title=dict(text=""),
            font=fonte_eixo,
        ),
        hoverlabel=dict(
            bgcolor=cor.surface,
            bordercolor=cor.border_strong,
            font=dict(family=tipo.font_family, size=tam_base, color=cor.text_primary),
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor=cor.border_strong,
            ticks="outside",
            tickcolor=cor.border_strong,
            tickfont=fonte_eixo,
            title=dict(font=fonte_eixo),
            automargin=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=cor.border,
            gridwidth=1,
            zeroline=False,
            showline=False,
            ticks="",
            tickfont=fonte_eixo,
            title=dict(font=fonte_eixo),
            automargin=True,
        ),
        colorscale=dict(
            sequential=[
                [0.0, cor.surface_alt],
                [0.5, cor.secondary],
                [1.0, cor.primary],
            ]
        ),
    )
    return go.layout.Template(layout=layout)


def registrar_template() -> None:
    """Registra (ou atualiza) o template `fx` em plotly.io. Idempotente; não altera o default global."""
    pio.templates[NOME_TEMPLATE] = construir_template()


def aplicar_template(fig: go.Figure) -> go.Figure:
    """Aplica o template `fx` à figura (registrando-o se necessário). Não altera os dados."""
    if NOME_TEMPLATE not in pio.templates:
        registrar_template()
    fig.update_layout(template=NOME_TEMPLATE)
    return fig