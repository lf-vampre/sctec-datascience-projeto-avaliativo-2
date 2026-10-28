"""Componente de UI para exibição de notas metodológicas estilizadas."""

import html
import streamlit as st

import src.config.methodology as methodology


# Mapeamento de chaves para constantes do modulo de metodologia
METODOLOGIA_MAP = {
    "juro_real": methodology.METHODOLOGY_JURO_REAL,
    "sharpe": methodology.METHODOLOGY_SHARPE,
    "bancos": methodology.METHODOLOGY_BANCOS,
    "DM-01": methodology.METHODOLOGY_JURO_REAL,
    "DM-02": methodology.METHODOLOGY_SHARPE,
}


def nota_metodologica(chave: str, titulo: str = "Nota Metodológica") -> None:
    """Exibe nota metodológica em expander a partir de uma chave cadastrada.
    
    Args:
        chave: Identificador da nota em methodology.py (ex: 'juro_real', 'sharpe', 'bancos').
        titulo: Rótulo do expander.
        
    Raises:
        KeyError: Se a chave fornecida não estiver cadastrada.
    """
    if chave not in METODOLOGIA_MAP:
        raise KeyError(
            f"Nota metodológica '{chave}' não encontrada em methodology.py. "
            f"Chaves disponíveis: {list(METODOLOGIA_MAP.keys())}"
        )

    texto_bruto = METODOLOGIA_MAP[chave]
    texto_seguro = html.escape(texto_bruto)

    with st.expander(f"ℹ️ {html.escape(titulo)}", expanded=False):
        st.markdown(
            f'<div class="fx-note">{texto_seguro}</div>',
            unsafe_allow_html=True,
        )