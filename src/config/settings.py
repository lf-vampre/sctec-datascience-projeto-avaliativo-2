"""Configurações centrais do sistema, séries temporais, parâmetros e TTLs."""

from typing import Any, Dict

# ------------------------------------------------------------------------------
# Séries SGS - BACEN
# ------------------------------------------------------------------------------
BACEN_SERIES: Dict[str, Dict[str, Any]] = {
    "SELIC_META": {
        "sgs_codigo": 432,
        "nome": "Taxa de juros - Selic Meta",
        "unidade": "% a.a.",
        "granularidade": "diária",
        "agg_mensal": "ultimo",
    },
    "SELIC_EFETIVA": {
        "sgs_codigo": 1178,
        "nome": "Taxa de juros - Selic Efetiva (over)",
        "unidade": "% a.a.",
        "granularidade": "diária",
        "agg_mensal": "ultimo",
    },
    "IPCA_MENSAL": {
        "sgs_codigo": 433,
        "nome": "Índice nacional de preços ao consumidor-amplo (IPCA)",
        "unidade": "%",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
    },
    "IPCA_12M": {
        "sgs_codigo": 13522,
        "nome": "IPCA acumulado nos últimos 12 meses",
        "unidade": "% a.a.",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
    },
    "PTAX_VENDA": {
        "sgs_codigo": 1,
        "nome": "Taxa de câmbio - Dólar americano (venda)",
        "unidade": "R$",
        "granularidade": "diária",
        "agg_mensal": "media",
    },
    "IBC_BR_SA": {
        "sgs_codigo": 24364,
        "nome": "Índice de Atividade Econômica do Banco Central (IBC-Br com ajuste)",
        "unidade": "Índice",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
    },
    "POUPANCA": {
        "sgs_codigo": 196,
        "nome": "Rendimento da caderneta de poupança",
        "unidade": "%",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
    },
}

# Série utilizada como taxa livre de risco nos cálculos de Sharpe e performance 
SERIE_RISCO_LIVRE: str = "SELIC_EFETIVA"

# ------------------------------------------------------------------------------
# Períodos Default
# ------------------------------------------------------------------------------
DEFAULT_BACEN_START_DATE: str = "2019-01-01"
DEFAULT_BACEN_END_DATE: str = "2023-12-31"

DEFAULT_B3_START_DATE: str = "2019-01-01"
# yfinance possui end exclusivo (01/01/2024 busca até 31/12/2023)
DEFAULT_B3_END_DATE: str = "2024-01-01"

DEFAULT_CVM_START_YEAR: int = 2019
DEFAULT_CVM_END_YEAR: int = 2023

# ------------------------------------------------------------------------------
# TTLs e Caches
# ------------------------------------------------------------------------------
CACHE_TTL_GOLD_SECONDS: int = 3600  # 1 hora para dados Ouro na UI
BRONZE_TTL_DAYS: int = 1            # Reutilização de coleta Bronze no DataOps

# ------------------------------------------------------------------------------
# Parâmetros Sandbox / DataOps
# ------------------------------------------------------------------------------
SANDBOX_MAX_TICKERS: int = 5
SANDBOX_MIN_INTERVAL_SECONDS: int = 30