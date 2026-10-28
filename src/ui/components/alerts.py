"""Componente de UI para exibição de avisos e alertas padronizados."""

import html
from typing import Optional
import streamlit as st

import src.config.methodology as methodology

TEXTO_NAO_CAUSALIDADE = (
    "As análises de correlação e regressão apresentadas indicam associação estatística "
    "e não estabelecem relação de causalidade direta entre as variáveis."
)


def aviso(tipo: str, texto: str) -> None:
    """Exibe mensagem de aviso estilizada de acordo com o tipo especificado.
    
    Args:
        tipo: 'info', 'atencao'/'warning' ou 'limitacao'/'error'.
        texto: Texto da mensagem de aviso.
    """
    texto_seguro = html.escape(texto)

    if tipo in ("info", "informacao"):
        st.info(texto_seguro)
    elif tipo in ("atencao", "warning"):
        st.warning(texto_seguro)
    elif tipo in ("limitacao", "error", "erro"):
        st.error(texto_seguro)
    else:
        st.info(texto_seguro)


def aviso_financeiras() -> None:
    """Exibe aviso padronizado sobre as limitações contábeis de instituições financeiras (ADR-09)."""
    st.warning(html.escape(methodology.METHODOLOGY_BANCOS))


def aviso_nao_causalidade() -> None:
    """Exibe aviso de não-causalidade analítica (RNF-12)."""
    st.caption(f"⚠️ {html.escape(TEXTO_NAO_CAUSALIDADE)}")