"""Textos e notas metodológicas exibidos na interface e documentação """

from src.config.settings import SERIE_RISCO_LIVRE, BACEN_SERIES

# ------------------------------------------------------------------------------
# Juro Real Ex-Post (Fisher Exato)
# ------------------------------------------------------------------------------
METHODOLOGY_JURO_REAL: str = (
    "Calculado pela equação de Fisher (exata): r_real = (1 + Selic Meta) / (1 + IPCA 12m) - 1. "
    "Diferente da subtração simples (Selic - IPCA), que superestima o juro real em cenários de taxas elevadas."
)

# ------------------------------------------------------------------------------
# Taxa Livre de Risco do Sharpe
# ------------------------------------------------------------------------------
_nome_risco_livre = BACEN_SERIES.get(SERIE_RISCO_LIVRE, {}).get("nome", SERIE_RISCO_LIVRE)

METHODOLOGY_SHARPE: str = (
    f"Taxa livre de risco utilizada: {SERIE_RISCO_LIVRE} ({_nome_risco_livre}), proxy do CDI. "
    "Cálculo baseado no excesso de retorno diário sobre o CDI anualizado pela raiz de 252 dias úteis. "
    "Os resultados dependem do recorte temporal selecionado."
)

# ------------------------------------------------------------------------------
# Limitações de Instituições Financeiras
# ------------------------------------------------------------------------------
METHODOLOGY_BANCOS: str = (
    "Instituições financeiras utilizam estrutura contábil própria (Plano COSIF). "
    "Indicadores como Margem EBIT, Liquidez Corrente e Dívida Líquida não se aplicam e são exibidos como N/A. "
    "A Receita de Intermediação Financeira é apresentada de forma isolada e não comparável com empresas industriais."
)