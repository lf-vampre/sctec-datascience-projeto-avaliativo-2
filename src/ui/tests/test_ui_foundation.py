import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

mock_streamlit = MagicMock()
mock_streamlit.session_state = {}
sys.modules["streamlit"] = mock_streamlit

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
    """Garante que init_state cria as chaves padrão se não existirem."""
    init_state()
    assert mock_streamlit.session_state["modo"] is None
    assert mock_streamlit.session_state["aba_ativa"] == "d1_macro"
    assert mock_streamlit.session_state["filtros"] == get_default_filtros()


def test_init_state_idempotent():
    """Garante que init_state não sobrescreve valores pré-existentes."""
    mock_streamlit.session_state["modo"] = "bi"
    mock_streamlit.session_state["aba_ativa"] = "d2_cvm"
    custom_filtros = {"periodo": (2020, 2022)}
    mock_streamlit.session_state["filtros"] = custom_filtros

    init_state()
    assert mock_streamlit.session_state["modo"] == "bi"
    assert mock_streamlit.session_state["aba_ativa"] == "d2_cvm"
    assert mock_streamlit.session_state["filtros"] == custom_filtros


def test_ir_para_e_voltar_landing():
    """Testa transições de modo e abas de navegação."""
    init_state()
    ir_para("bi", "d3_b3")
    assert mock_streamlit.session_state["modo"] == "bi"
    assert mock_streamlit.session_state["aba_ativa"] == "d3_b3"

    voltar_landing()
    assert mock_streamlit.session_state["modo"] is None


def test_reset_filtros():
    """Valida restauração dos filtros padrão."""
    init_state()
    mock_streamlit.session_state["filtros"] = {"periodo": (2022, 2023)}
    reset_filtros()
    assert mock_streamlit.session_state["filtros"] == get_default_filtros()


def test_inject_css_resilience_on_missing_file():
    """Garante que falha na leitura do arquivo CSS não lança exceção."""
    with patch("src.ui.styles.style_loader.ROOT_DIR", Path("/caminho_inexistente_teste")):
        inject_css()
        assert mock_streamlit.markdown.called