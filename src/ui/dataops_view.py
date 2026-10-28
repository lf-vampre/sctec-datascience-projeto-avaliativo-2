import streamlit as st
from src.ui.components.alerts import aviso
from src.ui.components.header import header


def render() -> None:
    """Renderiza a view temporária do DataOps Control Tower com componentes base."""
    header(
        titulo="⚙️ DataOps Control Tower",
        subtitulo="Orquestração e monitoramento do pipeline de dados.",
        mostrar_botao_voltar=True,
    )
    aviso("info", "Módulo em construção. Em breve painel de controle e logs de execução.")