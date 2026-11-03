import sys
import streamlit as st
from unittest.mock import patch, MagicMock
import pytest
import subprocess
from pathlib import Path

mock_streamlit = MagicMock()
mock_streamlit.session_state = {}
#sys.modules["streamlit"] = mock_streamlit

from src.ui.landing import render as render_landing
from src.ui.state import init_state, ir_para, voltar_landing

from unittest.mock import patch

@pytest.fixture(autouse=True)
def isolar_streamlit_mock():
    original = sys.modules.get("streamlit")
    yield
    if original is not None:
        sys.modules["streamlit"] = original
    else:
        sys.modules.pop("streamlit", None)


@pytest.fixture(autouse=True)
def clear_session_state():
    """Limpa o mock de session_state e ajusta o mock de st.columns antes de cada teste."""
    mock_streamlit.session_state.clear()
    mock_streamlit.columns.return_value = [MagicMock(), MagicMock()]


def test_landing_render_runs_without_exception():
    init_state()
    with patch("streamlit.markdown"), \
         patch("streamlit.columns", return_value=[MagicMock(), MagicMock()]), \
         patch("streamlit.button"):
        render_landing()


def test_landing_navigation_state_flow():
    """Testa transição de modos a partir das ações da landing page."""
    st.session_state.clear()
    init_state()
    assert st.session_state.get("modo") is None

    ir_para("dataops")
    assert st.session_state.get("modo") == "dataops"

    voltar_landing()
    assert st.session_state.get("modo") is None

    ir_para("bi")
    assert st.session_state.get("modo") == "bi"


def test_lazy_loading_import_isolation():
    """RNF-01: a landing não pode carregar ETL, loader, dashboards nem plotly."""
    root = Path(__file__).resolve().parents[3]
    code = (
        "import sys\n"
        "from unittest.mock import MagicMock\n"
        "sys.modules['streamlit'] = MagicMock()\n"
        "import src.ui.landing, src.ui.state\n"
        "heavy = ['src.etl', 'src.etl.pipeline', 'src.ui.data_loader', "
        "'src.ui.dashboards', 'plotly']\n"
        "loaded = [m for m in heavy if m in sys.modules]\n"
        "assert not loaded, f'carregados: {loaded}'\n"
    )
    res = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr