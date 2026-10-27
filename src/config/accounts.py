"""Mapeamento de contas contábeis CVM por tipo de plano (industrial vs. financeira)."""

from typing import Dict, List, Optional, TypedDict


class AccountSpecIndustrial(TypedDict):
    cd_conta: str
    ds_conta: str
    demonstrativo: str


class AccountSpecFinancial(TypedDict):
    cd_conta: Optional[str]
    keywords: List[str]
    demonstrativo: str


# Mapeamento para plano INDUSTRIAL / COMERCIAL (Mapeamento por CD_CONTA e ST_CONTA_FIXA = 'S')
INDUSTRIAL_ACCOUNTS: Dict[str, AccountSpecIndustrial] = {
    "RECEITA_LIQUIDA": {
        "cd_conta": "3.01",
        "ds_conta": "Receita de Venda de Bens e/ou Serviços",
        "demonstrativo": "DRE",
    },
    "LUCRO_BRUTO": {
        "cd_conta": "3.03",
        "ds_conta": "Resultado Bruto",
        "demonstrativo": "DRE",
    },
    "EBIT": {
        "cd_conta": "3.05",
        "ds_conta": "Resultado Antes do Resultado Financeiro e dos Impostos",
        "demonstrativo": "DRE",
    },
    "DESP_FINANCEIRAS": {
        "cd_conta": "3.06.02",
        "ds_conta": "Despesas Financeiras",
        "demonstrativo": "DRE",
    },
    "LUCRO_LIQUIDO": {
        "cd_conta": "3.11",
        "ds_conta": "Lucro/Prejuízo Consolidado do Período",
        "demonstrativo": "DRE",
    },
    "ATIVO_CIRCULANTE": {
        "cd_conta": "1.01",
        "ds_conta": "Ativo Circulante",
        "demonstrativo": "BPA",
    },
    "PASSIVO_CIRCULANTE": {
        "cd_conta": "2.01",
        "ds_conta": "Passivo Circulante",
        "demonstrativo": "BPP",
    },
    "CAIXA_EQUIV": {
        "cd_conta": "1.01.01",
        "ds_conta": "Caixa e Equivalentes de Caixa",
        "demonstrativo": "BPA",
    },
    "APLIC_FINANC": {
        "cd_conta": "1.01.02",
        "ds_conta": "Aplicações Financeiras",
        "demonstrativo": "BPA",
    },
    "EMPR_FIN_CP": {
        "cd_conta": "2.01.04",
        "ds_conta": "Empréstimos e Financiamentos",
        "demonstrativo": "BPP",
    },
    "EMPR_FIN_LP": {
        "cd_conta": "2.02.01",
        "ds_conta": "Empréstimos e Financiamentos",
        "demonstrativo": "BPP",
    },
    "PATRIMONIO_LIQUIDO": {
        "cd_conta": "2.03",
        "ds_conta": "Patrimônio Líquido Consolidado",
        "demonstrativo": "BPP",
    },
}

# Mapeamento para plano FINANCEIRO / BANCÁRIO (Restrito por cd_conta e busca em DS_CONTA)
FINANCIAL_ACCOUNTS: Dict[str, AccountSpecFinancial] = {
    "RECEITA_INTERMEDIACAO": {
        "cd_conta": "3.01",
        "keywords": [
            "receita de intermediação financeira",
            "receitas de intermediação financeira",
            "receitas da intermediação financeira",
        ],
        "demonstrativo": "DRE",
    },
    "LUCRO_LIQUIDO": {
        "cd_conta": "3.11",
        "keywords": [
            "lucro/prejuízo consolidado do período",
            "lucro líquido do período",
            "lucro/prejuízo do período",
        ],
        "demonstrativo": "DRE",
    },
    "PATRIMONIO_LIQUIDO": {
        "cd_conta": "2.03",
        "keywords": [
            "patrimônio líquido consolidado",
            "patrimônio líquido",
        ],
        "demonstrativo": "BPP",
    },
}