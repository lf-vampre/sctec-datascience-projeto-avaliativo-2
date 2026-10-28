"""Componente de cabeçalho padronizado para as páginas e visões da UI."""

import html
from typing import Optional
import streamlit as st

from src.ui.state import voltar_landing


def header(
    titulo: str,
    subtitulo: Optional[str] = None,
    mostrar_botao_voltar: bool = False,
) -> None:
    """Renderiza o cabeçalho padronizado da página com suporte a escape HTML.
    
    Args:
        titulo: Título principal da página.
        subtitulo: Subtítulo descritivo opcional.
        mostrar_botao_voltar: Exibe botão para retornar à landing page.
    """
    safe_titulo = html.escape(titulo)
    safe_subtitulo = html.escape(subtitulo) if subtitulo else None

    if mostrar_botao_voltar:
        if st.button("⬅️ Voltar ao Início", key=f"btn_header_voltar_{safe_titulo}"):
            voltar_landing()
            st.rerun()

    sub_html = f'<p class="fx-header-subtitle">{safe_subtitulo}</p>' if safe_subtitulo else ""

    st.markdown(
        f"""
        <div class="fx-header-block">
            <h1 class="fx-header-title">{safe_titulo}</h1>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )