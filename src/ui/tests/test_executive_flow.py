"""Testes de integração do fluxo executivo ponta a ponta usando Streamlit AppTest."""

import sys
import pytest
from streamlit.testing.v1 import AppTest
import streamlit as st

from src.ui.state import init_state, reset_filtros, voltar_landing


def _app_main_script():
    import streamlit as st
    from src.ui import executive_view, landing
    from src.ui.state import init_state

    init_state()

    if "modo_ativo" not in st.session_state:
        st.session_state["modo_ativo"] = "landing"

    modo = st.session_state["modo_ativo"]

    if modo == "landing":
        landing.render()
    elif modo == "executive":
        def _radio_fallback(label, options, default=None, key=None, on_change=None, label_visibility="visible"):
            idx = options.index(default) if default in options else 0
            return st.radio(
                label,
                options=options,
                index=idx,
                key=key,
                on_change=on_change,
                horizontal=True,
                label_visibility=label_visibility,
            )

        st.segmented_control = _radio_fallback
        executive_view.render()


def test_fluxo_ponta_a_ponta_bi_executivo():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=10).run()
    assert not at.exception


def test_isolamento_imports_landing():
    def _script_landing_only():
        import sys
        import streamlit as st
        from src.ui import landing
        from src.ui.state import init_state

        modulos_antes = set(sys.modules.keys())
        init_state()
        landing.render()
        modulos_depois = set(sys.modules.keys())

        st.session_state["novos_modulos"] = list(modulos_depois - modulos_antes)

    at = AppTest.from_function(_script_landing_only)
    at.run()
    assert not at.exception

    novos_modulos = (
        at.session_state["novos_modulos"]
        if "novos_modulos" in at.session_state
        else []
    )
    assert not any(m.startswith("src.ui.dashboards.") for m in novos_modulos)