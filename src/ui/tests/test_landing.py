import sys
from unittest.mock import MagicMock
import pytest
import subprocess
from pathlib import Path

mock_streamlit = MagicMock()
mock_streamlit.session_state = {}
sys.modules["streamlit"] = mock_streamlit

from src.ui.landing import render as render_landing
from src.ui.state import init_state, ir_para, voltar_landing


@pytest.fixture(autouse=True)
def clear_session_state():
    """Limpa o mock de session_state e ajusta o mock de st.columns antes de cada teste."""
    mock_streamlit.session_state.clear()
    mock_streamlit.columns.return_value = [MagicMock(), MagicMock()]


def test_landing_render_runs_without_exception():
    """Garante que a landing page renderiza sem erros."""
    init_state()
    render_landing()
    assert mock_streamlit.markdown.called


def test_landing_navigation_state_flow():
    """Testa transição de modos a partir das ações da landing page."""
    init_state()
    assert mock_streamlit.session_state["modo"] is None

    ir_para("dataops")
    assert mock_streamlit.session_state["modo"] == "dataops"

    voltar_landing()
    assert mock_streamlit.session_state["modo"] is None

    ir_para("bi")
    assert mock_streamlit.session_state["modo"] == "bi"


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