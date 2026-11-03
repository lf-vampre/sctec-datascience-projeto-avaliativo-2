import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import streamlit as st

mock_streamlit = MagicMock()
mock_streamlit.session_state = {}
# sys.modules["streamlit"] = mock_streamlit

@pytest.fixture(autouse=True)
def isolar_streamlit_mock():
    original = sys.modules.get("streamlit")
    yield
    if original is not None:
        sys.modules["streamlit"] = original
    else:
        sys.modules.pop("streamlit", None)

from src.config.theme import (
    COLOR_TOKENS,
    ELEVATION_TOKENS,
    GEOMETRY_TOKENS,
    TYPOGRAPHY_TOKENS,
    generate_css_variables,
)
from src.ui.state import (
    get_default_filtros,
    init_state,
    ir_para,
    reset_filtros,
    voltar_landing,
)
from src.ui.styles.style_loader import inject_css


@pytest.fixture(autouse=True)
def clear_session_state():
    """Limpa o mock de session_state antes de cada teste."""
    mock_streamlit.session_state.clear()


def test_theme_generate_css_variables():
    """Valida a geração de variáveis CSS a partir dos tokens."""
    css_vars = generate_css_variables()
    assert ":root {" in css_vars
    assert f"--fx-color-primary: {COLOR_TOKENS.primary}" in css_vars
    assert f"--fx-font-family: {TYPOGRAPHY_TOKENS.font_family}" in css_vars
    assert f"--fx-radius-md: {GEOMETRY_TOKENS.radius_md}" in css_vars
    assert f"--fx-shadow-sm: {ELEVATION_TOKENS.shadow_sm}" in css_vars


def test_init_state_creates_defaults():
    import streamlit as st
    from src.ui.state import init_state

    st.session_state.clear()
    init_state()
    assert st.session_state.get("modo") in (None, "landing", "executive", "dataops")

def test_init_state_idempotent():
    st.session_state["modo"] = "bi"
    st.session_state["aba_ativa"] = "d2_cvm"
    custom_filtros = {"periodo": (2020, 2022)}
    st.session_state["filtros"] = custom_filtros

    init_state()
    assert st.session_state["modo"] == "bi"
    assert st.session_state["aba_ativa"] == "d2_cvm"
    assert st.session_state["filtros"] == custom_filtros


def test_ir_para_e_voltar_landing():
    init_state()
    ir_para("bi", "d3_b3")
    assert st.session_state["modo"] == "bi"
    assert st.session_state["aba_ativa"] == "d3_b3"

    voltar_landing()
    assert st.session_state.get("modo") is None


def test_reset_filtros():
    init_state()
    reset_filtros()
    assert "periodo" in st.session_state.filtros
    assert "tickers" in st.session_state.filtros


def test_inject_css_resilience_on_missing_file(tmp_path):
    # inject_css() não aceita argumentos; patch do caminho do CSS para simular arquivo inexistente
    with patch("src.ui.styles.style_loader.ROOT_DIR", tmp_path):
        inject_css()