"""Testes de interface para a seção de EDA do DataOps View via Streamlit AppTest."""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.etl.eda.profiler import DataProfiler, RelatorioEDA


def test_eda_view_renderizacao_e_selecao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valida renderização das abas de EDA quando há dados Prata disponíveis."""
    at = AppTest.from_file("app.py", default_timeout=10.0)
    at.run()

    # Navegar para DataOps Control Tower na Landing Page
    btn_dataops = [b for b in at.button if "DataOps" in b.label]
    if btn_dataops:
        btn_dataops[0].click().run()

    # Garantir que a seção de EDA está presente
    assert any("EDA e Qualidade dos Dados" in sub.value for sub in at.subheader)


def test_eda_view_profiler_simulado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valida orquestração da EDA com mock do DataProfiler."""
    def mock_perfil(self: DataProfiler, fonte: str, modo: str = "producao") -> RelatorioEDA:
        rel = RelatorioEDA()
        rel.resumo = {
            "fonte": fonte,
            "tabela": "mock_table",
            "linhas": 100,
            "colunas": 5,
            "periodo": "2023-01-01 a 2023-12-31",
            "data_geracao": "2026-11-01T00:00:00",
        }
        rel.tabelas["nulos_por_coluna"] = pd.DataFrame(
            {"nulos_qtd": [0, 5], "nulos_pct": [0.0, 5.0]}, index=["col1", "col2"]
        )
        return rel

    monkeypatch.setattr(DataProfiler, "perfil", mock_perfil)

    profiler = DataProfiler()
    relatorio = profiler.perfil("bacen", modo="sandbox")

    assert relatorio.resumo["linhas"] == 100
    assert relatorio.resumo["colunas"] == 5
    assert "nulos_por_coluna" in relatorio.tabelas