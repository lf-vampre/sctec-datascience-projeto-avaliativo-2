import streamlit as st

# Configuração da página precisa ser o primeiro comando Streamlit executado
st.set_page_config(
    page_title="Plataforma Financeira Integrada",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.ui.state import init_state
from src.ui.styles.style_loader import inject_css


def main() -> None:
    """Ponto de entrada principal com roteamento lazy por modo."""
    inject_css()
    init_state()

    modo = st.session_state.get("modo")

    if modo == "dataops":
        from src.ui.dataops_view import render as render_dataops

        render_dataops()
    elif modo == "bi":
        from src.ui.executive_view import render as render_executive

        render_executive()
    else:
        from src.ui.landing import render as render_landing

        render_landing()


if __name__ == "__main__":
    main()