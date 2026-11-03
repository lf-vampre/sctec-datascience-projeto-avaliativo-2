import html
import sys
from unittest.mock import MagicMock, patch
import pytest

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

from src.ui.components.alerts import (
    TEXTO_NAO_CAUSALIDADE,
    aviso,
    aviso_financeiras,
    aviso_nao_causalidade,
)
from src.ui.components.header import header
from src.ui.components.kpi import kpi
from src.ui.components.notes import METODOLOGIA_MAP, nota_metodologica


@pytest.fixture(autouse=True)
def clear_mocks():
    """Reseta estados e chamadas de mocks do Streamlit antes de cada teste."""
    mock_streamlit.reset_mock()
    mock_streamlit.session_state.clear()


def test_kpi_formatting_and_null_handling():
    with patch("streamlit.metric") as mock_metric:
        kpi(label="Receita", valor=1234.56, formato="moeda", ajuda="Ajuda")
        mock_metric.assert_called_with(label="Receita", value="R$ 1.234,56", delta=None, help="Ajuda")

        kpi(label="Margem", valor=12.34, formato="percentual")
        mock_metric.assert_called_with(label="Margem", value="12,34%", delta=None, help=None)

        kpi(label="Volume", valor=None)
        mock_metric.assert_called_with(label="Volume", value="—", delta=None, help=None)


def test_header_escaping_and_render():
    with patch("streamlit.markdown") as mock_markdown:
        header(titulo="<script>alert(1)</script>", subtitulo="<b>Sub</b>")
        assert mock_markdown.called
        call_arg = mock_markdown.call_args[0][0]
        assert html.escape("<script>alert(1)</script>") in call_arg
        assert html.escape("<b>Sub</b>") in call_arg


def test_nota_metodologica_valid_key_and_error():
    with patch("streamlit.markdown") as mock_markdown:
        nota_metodologica("DM-01")
        assert mock_markdown.called

    with pytest.raises(KeyError):
        nota_metodologica("chave_inexistente_123")


def test_alerts_rendering():
    with patch("streamlit.info") as mock_info, \
         patch("streamlit.warning") as mock_warning, \
         patch("streamlit.caption") as mock_caption:
        
        aviso("info", "Mensagem Informativa")
        mock_info.assert_called_with("Mensagem Informativa")

        aviso("atencao", "Aviso de Atenção")
        mock_warning.assert_called_with("Aviso de Atenção")

        aviso_financeiras()
        assert mock_warning.called

        aviso_nao_causalidade()
        assert mock_caption.called