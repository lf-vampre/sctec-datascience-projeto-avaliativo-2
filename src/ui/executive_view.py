import streamlit as st
from src.ui.state import voltar_landing


def render() -> None:
    """Renderiza a view temporária do BI Executivo."""
    st.title("📊 Data App BI Executivo")
    st.info("Módulo em construção.")
    if st.button("⬅️ Voltar ao Início", key="btn_voltar_executive"):
        voltar_landing()
        st.rerun()