"""Mapeamento do universo de empresas, tickers, CVM, setores e flags."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CompanyInfo:
    ticker: str
    cd_cvm: int
    denom_cia: str
    setor_analitico: str
    tipo_plano: str  # "industrial" ou "financeira"
    exportadora_commodities: bool
    tem_cvm: bool = True
    tem_b3: bool = True


# Mapeamento do universo: 15 tickers do PDF + 4 extras (BBAS3, SANB11, EQTL3, SBSP3)
COMPANIES: Dict[str, CompanyInfo] = {
    # Indústria & Bens de Capital
    "WEGE3": CompanyInfo("WEGE3", 5410, "WEG S.A.", "Indústria & Bens de Capital", "industrial", False),
    "EMBR3": CompanyInfo("EMBR3", 18325, "EMBRAER S.A.", "Indústria & Bens de Capital", "industrial", False),

    # Materiais Básicos
    "VALE3": CompanyInfo("VALE3", 4170, "VALE S.A.", "Materiais Básicos", "industrial", True),
    "GGBR4": CompanyInfo("GGBR4", 3310, "GERDAU S.A.", "Materiais Básicos", "industrial", True),
    "KLBN11": CompanyInfo("KLBN11", 14451, "KLABIN S.A.", "Materiais Básicos", "industrial", True),
    "SUZB3": CompanyInfo("SUZB3", 13749, "SUZANO S.A.", "Materiais Básicos", "industrial", True),

    # Energia
    "PETR4": CompanyInfo("PETR4", 9512, "PETROLEO BRASILEIRO S.A. PETROBRAS", "Energia", "industrial", True),
    "PRIO3": CompanyInfo("PRIO3", 21750, "PRIO S.A.", "Energia", "industrial", True),
    "EGIE3": CompanyInfo("EGIE3", 17329, "ENGIE BRASIL ENERGIA S.A.", "Energia", "industrial", False),
    "EQTL3": CompanyInfo("EQTL3", 20087, "EQUATORIAL ENERGIA S.A.", "Energia", "industrial", False),

    # Financeiro
    "ITUB4": CompanyInfo("ITUB4", 19348, "ITAU UNIBANCO HOLDING S.A.", "Financeiro", "financeira", False),
    "BBDC4": CompanyInfo("BBDC4", 906, "BANCO BRADESCO S.A.", "Financeiro", "financeira", False),
    "BBAS3": CompanyInfo("BBAS3", 1023, "BANCO DO BRASIL S.A.", "Financeiro", "financeira", False),
    "SANB11": CompanyInfo("SANB11", 21237, "BANCO SANTANDER (BRASIL) S.A.", "Financeiro", "financeira", False),

    # Consumo & Varejo/Serviços
    "ABEV3": CompanyInfo("ABEV3", 23264, "AMBEV S.A.", "Consumo & Varejo/Serviços", "industrial", False),
    "JBSS3": CompanyInfo("JBSS3", 20575, "JBS S.A.", "Consumo & Varejo/Serviços", "industrial", True),
    "LREN3": CompanyInfo("LREN3", 19283, "LOJAS RENNER S.A.", "Consumo & Varejo/Serviços", "industrial", False),
    "RENT3": CompanyInfo("RENT3", 19216, "LOCALIZA RENT A CAR S.A.", "Consumo & Varejo/Serviços", "industrial", False),
    "SBSP3": CompanyInfo("SBSP3", 14443, "CIA SANEAMENTO BASICO DO ESTADO DE SAO PAULO", "Consumo & Varejo/Serviços", "industrial", False),
}


def validate_universe() -> bool:
    """Valida a regra de 1 ticker por cd_cvm no universo cadastrado."""
    cvm_codes: List[int] = [info.cd_cvm for info in COMPANIES.values()]
    unique_codes = set(cvm_codes)
    if len(cvm_codes) != len(unique_codes):
        duplicated = [code for code in cvm_codes if cvm_codes.count(code) > 1]
        raise ValueError(f"Divergência no universo: CD_CVM duplicado encontrado ({duplicated})")
    return True


# Validação na importação do módulo
validate_universe()