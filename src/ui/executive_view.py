import streamlit as st
from src.ui.components.alerts import aviso
from src.ui.components.header import header


def render() -> None:
    """Renderiza a view temporária do BI Executivo com componentes base."""
    header(
        titulo="📊 Data App BI Executivo",
        subtitulo="Painéis analíticos e visões consolidadas da Tríade.",
        mostrar_botao_voltar=True,
    )
    aviso("info", "Módulo em construção. Em breve painéis analíticos interativos.")