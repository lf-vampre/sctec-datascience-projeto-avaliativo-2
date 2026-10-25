"""Mapeamento de contas da CVM por tipo de plano (industrial vs financeira).

    NOTA: Códigos e descrições a validar contra dados reais (CvmCleaner).
"""

from typing import Dict, List

# ------------------------------------------------------------------------------
# Plano Industrial / Comercial (Mapeamento via CD_CONTA fixo)
# ------------------------------------------------------------------------------
INDUSTRIAL_ACCOUNTS: Dict[str, str] = {
    # DRE
    "3.01": "RECEITA_LIQUIDA",
    "3.03": "LUCRO_BRUTO",
    "3.05": "EBIT",
    "3.06.02": "DESP_FINANCEIRAS",
    "3.11": "LUCRO_LIQUIDO",
    # BPA
    "1.01": "ATIVO_CIRCULANTE",
    "1.01.01": "CAIXA_EQUIV",
    "1.01.02": "APLIC_FINANC",
    # BPP
    "2.01": "PASSIVO_CIRCULANTE",
    "2.01.04": "EMPR_FIN_CP",
    "2.02.01": "EMPR_FIN_LP",
    "2.03": "PATRIMONIO_LIQUIDO",
}

# ------------------------------------------------------------------------------
# Plano Financeiro (Mapeamento via busca textual em DS_CONTA)
# ------------------------------------------------------------------------------
FINANCIAL_ACCOUNTS_KEYWORDS: Dict[str, List[str]] = {
    "RECEITA_INTERMEDIACAO": [
        "receitas da intermediação financeira",
        "receita de intermediação financeira",
        "receita operacional",
    ],
    "LUCRO_LIQUIDO": [
        "lucro/prejuízo consolidado do período",
        "lucro líquido do período",
        "lucro/prejuízo do período",
    ],
    "PATRIMONIO_LIQUIDO": [
        "patrimônio líquido",
        "patrimônio líquido consolidado",
    ],
}