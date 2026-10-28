import logging
from pathlib import Path
import streamlit as st

from src.config.theme import generate_css_variables
from src.utils.paths import ROOT_DIR

logger = logging.getLogger(__name__)


def inject_css() -> None:
    """Injeta as variáveis CSS e os estilos do theme.css no Streamlit.
    
    Falhas na leitura do arquivo ou na injeção são capturadas para garantir
    que a aplicação continue funcional com o tema nativo.
    """
    try:
        css_vars = generate_css_variables()
        css_path = ROOT_DIR / "src" / "ui" / "styles" / "theme.css"

        css_content = ""
        if css_path.is_file():
            css_content = css_path.read_text(encoding="utf-8")

        full_css = f"<style>\n{css_vars}\n{css_content}\n</style>"
        st.markdown(full_css, unsafe_allow_html=True)
    except Exception as exc:
        logger.warning("Falha ao injetar CSS customizado: %s", exc)