"""Testes de integração do componente de sidebar global usando Streamlit AppTest."""

import pytest
from streamlit.testing.v1 import AppTest

from src.models.contracts import Filtros
from src.ui.state import init_state, montar_filtros, reset_filtros


def _app_script():
    import streamlit as st
    from src.ui.sidebar import render
    from src.ui.state import init_state

    init_state()
    filtros = render()
    st.write(f"TICKERS_COUNT:{len(filtros.tickers)}")
    st.write(f"SETORES_COUNT:{len(filtros.setores)}")


def test_sidebar_defaults():
    at = AppTest.from_function(_app_script)
    at.run()
    assert not at.exception

    f = montar_filtros()
    assert len(f.tickers) > 0
    assert len(f.setores) > 0
    assert isinstance(f, Filtros)
    assert isinstance(hash(f), int)


def test_sidebar_filtro_cruzado_setores():
    def _script_setores():
        import streamlit as st
        from src.ui.sidebar import render
        from src.ui.state import init_state

        init_state()
        st.session_state["filtros"]["setores"] = ["Financeiro"]
        render()

    at = AppTest.from_function(_script_setores)
    at.run()
    assert not at.exception

    tickers = at.session_state["filtros"]["tickers"]
    assert "ITUB4" in tickers
    assert "VALE3" not in tickers


def test_sidebar_reset():
    def _script_reset():
        import streamlit as st
        from src.ui.sidebar import render
        from src.ui.state import init_state, reset_filtros

        init_state()
        st.session_state["filtros"]["setores"] = ["Energia"]
        reset_filtros()
        render()

    at = AppTest.from_function(_script_reset)
    at.run()
    assert not at.exception

    setores = at.session_state["filtros"]["setores"]
    assert len(setores) > 1


def test_sidebar_selecao_vazia_warning():
    def _script_vazio():
        import streamlit as st
        from src.ui.sidebar import render
        from src.ui.state import init_state

        init_state()
        st.session_state["filtros"]["tickers"] = []
        render()

    at = AppTest.from_function(_script_vazio)
    at.run()
    assert not at.exception
    assert len(at.warning) > 0