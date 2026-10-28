import streamlit as st
from src.ui.state import voltar_landing


def render() -> None:
    """Renderiza a view temporária do DataOps Control Tower."""
    st.title("⚙️ DataOps Control Tower")
    st.info("Módulo em construção.")
    if st.button("⬅️ Voltar ao Início", key="btn_voltar_dataops"):
        voltar_landing()
        st.rerun()