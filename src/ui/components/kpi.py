"""Componente de KPI baseado no st.metric nativo com formatação em pt-BR."""

from typing import Optional, Union
import streamlit as st

from src.utils.formatting import format_currency, format_number, format_percent

Numeric = Union[int, float]


def kpi(
    label: str,
    valor: Optional[Numeric] = None,
    delta: Optional[Union[Numeric, str]] = None,
    formato: str = "numero",
    ajuda: Optional[str] = None,
) -> None:
    """Wrapper padronizado sobre st.metric com suporte a formatação pt-BR e valores nulos.
    
    Args:
        label: Título descritivo do KPI.
        valor: Valor numérico a ser formatado ou None.
        delta: Variação (opcional) para exibição de seta/cor.
        formato: 'moeda', 'moeda_compacta', 'percentual' ou 'numero'.
        ajuda: Texto explicativo de tooltip (help).
    """
    if valor is None:
        val_str = "—"
    elif formato == "moeda":
        val_str = format_currency(valor)
    elif formato == "moeda_compacta":
        val_str = format_currency(valor, compact=True)
    elif formato == "percentual":
        val_str = format_percent(valor)
    else:
        val_str = format_number(valor)

    delta_str = str(delta) if delta is not None else None

    st.metric(
        label=label,
        value=val_str,
        delta=delta_str,
        help=ajuda,
    )