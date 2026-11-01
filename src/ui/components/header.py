"""Componente de cabeçalho padronizado para as páginas e visões da UI."""

import html
from typing import Optional
import streamlit as st

from src.ui.data_loader import neon_disponivel
from src.ui.state import voltar_landing


def header(
    titulo: str,
    subtitulo: Optional[str] = None,
    mostrar_botao_voltar: bool = False,
    mostrar_indicador_conexao: bool = False,
) -> None:
    """Renderiza o cabeçalho padronizado da página com suporte a escape HTML e indicador de conexão.
    
    Args:
        titulo: Título principal da página.
        subtitulo: Subtítulo descritivo opcional.
        mostrar_botao_voltar: Exibe botão para retornar à landing page.
        mostrar_indicador_conexao: Exibe indicador do status da fonte de dados (Neon / Fallback Parquet).
    """
    safe_titulo = html.escape(titulo)
    safe_subtitulo = html.escape(subtitulo) if subtitulo else None

    if mostrar_botao_voltar:
        if st.button("⬅️ Voltar ao Início", key=f"btn_header_voltar_{safe_titulo}"):
            voltar_landing()
            st.rerun()

    sub_html = f'<p class="fx-header-subtitle">{safe_subtitulo}</p>' if safe_subtitulo else ""

    indicador_html = ""
    if mostrar_indicador_conexao:
        is_neon = neon_disponivel()
        status_texto = "🟢 Neon" if is_neon else "🟠 Fallback Parquet"
        badge_class = "fx-badge-success" if is_neon else "fx-badge-warning"
        indicador_html = f'<span class="fx-badge {badge_class}" style="margin-left: 10px; vertical-align: middle;">{status_texto}</span>'

    st.markdown(
        f"""
        <div class="fx-header-block" style="margin-top:-20px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <h1 class="fx-header-title" style="margin: 0; display: inline-block;">{safe_titulo}</h1>
                {indicador_html}
            </div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )