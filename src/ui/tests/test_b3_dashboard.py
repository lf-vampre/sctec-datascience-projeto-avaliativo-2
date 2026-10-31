"""Testes unitários e de integração de layout/storytelling para b3_dashboard."""

import pandas as pd
import pytest

from src.models.contracts import Filtros
from src.ui.prep.market_story import gerar_story_mercado


def test_market_story_sem_termos_causais_ou_recomendacao():
    kpis = {
        "retorno_medio_carteira": 0.15,
        "volatilidade_media": 0.20,
        "ativo_destaque": "PETR4",
        "ativo_destaque_retorno": 0.35,
        "ativo_pior": "VALE3",
        "ativo_pior_retorno": -0.05,
    }

    tabela_rr = pd.DataFrame([
        {"ticker": "PETR4", "sharpe": 0.85, "drawdown_maximo": -0.10},
        {"ticker": "VALE3", "sharpe": 0.20, "drawdown_maximo": -0.25},
        {"ticker": "Carteira", "sharpe": 0.60, "drawdown_maximo": -0.12},
    ])

    story = gerar_story_mercado(kpis, tabela_rr)

    texto_completo = f"{story['contexto']} {story['insight']} {story['acao']}".lower()

    # Termos proibidos por regras de governança e compliance
    proibidos = ["compre", "venda", "causou", "portanto provocou", "motivado por"]
    for termo in proibidos:
        assert termo not in texto_completo, f"Termo proibido encontrado: '{termo}'"

    # Verificação de presença de números reais passados via KPI/Tabela
    assert "petr4" in texto_completo
    assert "vale3" in texto_completo