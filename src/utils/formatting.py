"""Utilitários de formatação de valores numéricos, moeda e porcentagem (pt-BR)."""

from typing import Optional, Union

Numeric = Union[int, float]


def format_currency(val: Optional[Numeric], decimal_places: int = 2) -> str:
    """Formata número para moeda Real Brasileira (R$). Ex: 1234.5 -> 'R$ 1.234,50'."""
    if val is None:
        return "N/A"
    try:
        formatted = f"{val:,.{decimal_places}f}"
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"
    except (ValueError, TypeError):
        return "N/A"


def format_percent(val: Optional[Numeric], decimal_places: int = 2, is_ratio: bool = False) -> str:
    """
    Formata número para porcentagem (%). Ex: 0.1234 (is_ratio=True) -> '12,34%' | 12.34 -> '12,34%'.
    """
    if val is None:
        return "N/A"
    try:
        number = val * 100.0 if is_ratio else val
        formatted = f"{number:,.{decimal_places}f}"
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted}%"
    except (ValueError, TypeError):
        return "N/A"


def format_number(val: Optional[Numeric], decimal_places: int = 2) -> str:
    """Formata número genérico com separador de milhar pt-BR. Ex: 1234.56 -> '1.234,56'."""
    if val is None:
        return "N/A"
    try:
        formatted = f"{val:,.{decimal_places}f}"
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except (ValueError, TypeError):
        return "N/A"