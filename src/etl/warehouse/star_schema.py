"""Construção e gestão das dimensões e fatos da camada Ouro (Star Schema)."""

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config import accounts, settings, universe
from src.etl.base import PipelineLogger
from src.etl.warehouse.metrics_calculator import (
    crescimento,
    divida_bruta,
    divida_liquida,
    juro_real_fisher,
    liquidez_corrente,
    margem_ebit,
    margem_liquida,
    retorno_diario,
    roe,
    sma,
)
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


INDICADOR_SEED: List[Dict[str, Any]] = [
    {
        "sk_indicador": 1,
        "codigo": "SELIC_META",
        "nome": "Taxa de juros - Selic Meta",
        "fonte": "BACEN",
        "tipo": "bruto",
        "unidade": "% a.a.",
        "granularidade": "diária",
        "agg_mensal": "ultimo",
        "sgs_codigo": 432,
        "cd_conta": None,
        "regra_calculo": "Taxa meta fixada pelo COPOM (SGS 432).",
    },
    {
        "sk_indicador": 2,
        "codigo": "SELIC_EFETIVA",
        "nome": "Taxa de juros - Selic Efetiva (over)",
        "fonte": "BACEN",
        "tipo": "bruto",
        "unidade": "% a.a.",
        "granularidade": "diária",
        "agg_mensal": "ultimo",
        "sgs_codigo": 1178,
        "cd_conta": None,
        "regra_calculo": "Taxa ponderada das operações compromissadas diárias (SGS 1178).",
    },
    {
        "sk_indicador": 3,
        "codigo": "IPCA_MENSAL",
        "nome": "IPCA Mensal",
        "fonte": "BACEN",
        "tipo": "bruto",
        "unidade": "%",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
        "sgs_codigo": 433,
        "cd_conta": None,
        "regra_calculo": "Variação percentual mensal do IPCA (SGS 433).",
    },
    {
        "sk_indicador": 4,
        "codigo": "IPCA_12M",
        "nome": "IPCA Acumulado 12M",
        "fonte": "BACEN",
        "tipo": "bruto",
        "unidade": "% a.a.",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
        "sgs_codigo": 13522,
        "cd_conta": None,
        "regra_calculo": "Variação acumulada do IPCA nos últimos 12 meses (SGS 13522).",
    },
    {
        "sk_indicador": 5,
        "codigo": "PTAX_VENDA",
        "nome": "Taxa de Câmbio - Dólar (Venda)",
        "fonte": "BACEN",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "diária",
        "agg_mensal": "media",
        "sgs_codigo": 1,
        "cd_conta": None,
        "regra_calculo": "Cotação de venda do dólar americano divulgada pelo BACEN (SGS 1).",
    },
    {
        "sk_indicador": 6,
        "codigo": "IBC_BR_SA",
        "nome": "IBC-Br com Ajuste Sazonal",
        "fonte": "BACEN",
        "tipo": "bruto",
        "unidade": "Índice",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
        "sgs_codigo": 24364,
        "cd_conta": None,
        "regra_calculo": "Índice de atividade econômica do Banco Central dessazonalizado (SGS 24364).",
    },
    {
        "sk_indicador": 7,
        "codigo": "POUPANCA",
        "nome": "Rendimento da Poupança",
        "fonte": "BACEN",
        "tipo": "bruto",
        "unidade": "%",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
        "sgs_codigo": 196,
        "cd_conta": None,
        "regra_calculo": "Rendimento da caderneta de poupança (SGS 196).",
    },
    {
        "sk_indicador": 8,
        "codigo": "JURO_REAL_EXPOST",
        "nome": "Juro Real Ex-Post (Fisher)",
        "fonte": "BACEN",
        "tipo": "derivado",
        "unidade": "% a.a.",
        "granularidade": "mensal",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Fórmula exata de Fisher: (1 + Selic Meta / 100) / (1 + IPCA 12M / 100) - 1.",
    },
    {
        "sk_indicador": 9,
        "codigo": "RECEITA_LIQUIDA",
        "nome": "Receita Líquida de Vendas",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "soma",
        "sgs_codigo": None,
        "cd_conta": "3.01",
        "regra_calculo": "DRE conta 3.01 (Plano Industrial).",
    },
    {
        "sk_indicador": 10,
        "codigo": "LUCRO_BRUTO",
        "nome": "Resultado Bruto",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "soma",
        "sgs_codigo": None,
        "cd_conta": "3.03",
        "regra_calculo": "DRE conta 3.03 (Plano Industrial).",
    },
    {
        "sk_indicador": 11,
        "codigo": "EBIT",
        "nome": "EBIT (Resultado Operacional)",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "soma",
        "sgs_codigo": None,
        "cd_conta": "3.05",
        "regra_calculo": "DRE conta 3.05 (Resultado Antes do Resultado Financeiro e Impostos).",
    },
    {
        "sk_indicador": 12,
        "codigo": "DESP_FINANCEIRAS",
        "nome": "Despesas Financeiras",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "soma",
        "sgs_codigo": None,
        "cd_conta": "3.06.02",
        "regra_calculo": "DRE conta 3.06.02 (Despesas Financeiras).",
    },
    {
        "sk_indicador": 13,
        "codigo": "LUCRO_LIQUIDO",
        "nome": "Lucro ou Prejuízo Líquido",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "soma",
        "sgs_codigo": None,
        "cd_conta": "3.11",
        "regra_calculo": "DRE conta 3.11 (Lucro/Prejuízo Consolidado do Período).",
    },
    {
        "sk_indicador": 14,
        "codigo": "ATIVO_CIRCULANTE",
        "nome": "Ativo Circulante",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": "1.01",
        "regra_calculo": "BPA conta 1.01.",
    },
    {
        "sk_indicador": 15,
        "codigo": "PASSIVO_CIRCULANTE",
        "nome": "Passivo Circulante",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": "2.01",
        "regra_calculo": "BPP conta 2.01.",
    },
    {
        "sk_indicador": 16,
        "codigo": "CAIXA_EQUIV",
        "nome": "Caixa e Equivalentes de Caixa",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": "1.01.01",
        "regra_calculo": "BPA conta 1.01.01.",
    },
    {
        "sk_indicador": 17,
        "codigo": "APLIC_FINANC",
        "nome": "Aplicações Financeiras",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": "1.01.02",
        "regra_calculo": "BPA conta 1.01.02.",
    },
    {
        "sk_indicador": 18,
        "codigo": "EMPR_FIN_CP",
        "nome": "Empréstimos e Financiamentos CP",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": "2.01.04",
        "regra_calculo": "BPP conta 2.01.04.",
    },
    {
        "sk_indicador": 19,
        "codigo": "EMPR_FIN_LP",
        "nome": "Empréstimos e Financiamentos LP",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": "2.02.01",
        "regra_calculo": "BPP conta 2.02.01.",
    },
    {
        "sk_indicador": 20,
        "codigo": "PATRIMONIO_LIQUIDO",
        "nome": "Patrimônio Líquido Consolidado",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": "2.03",
        "regra_calculo": "BPP conta 2.03.",
    },
    {
        "sk_indicador": 21,
        "codigo": "RECEITA_INTERMEDIACAO",
        "nome": "Receita de Intermediação Financeira",
        "fonte": "CVM",
        "tipo": "bruto",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "soma",
        "sgs_codigo": None,
        "cd_conta": "3.01",
        "regra_calculo": "DRE conta 3.01 para Instituições Financeiras (não comparável com empresas industriais).",
    },
    {
        "sk_indicador": 22,
        "codigo": "MARGEM_LIQUIDA",
        "nome": "Margem Líquida",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "fração",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Lucro Líquido / Receita Líquida (fração).",
    },
    {
        "sk_indicador": 23,
        "codigo": "MARGEM_EBIT",
        "nome": "Margem EBIT",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "fração",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "EBIT / Receita Líquida (fração).",
    },
    {
        "sk_indicador": 24,
        "codigo": "ROE",
        "nome": "Return on Equity (ROE)",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "fração",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Lucro Líquido / Patrimônio Líquido (fim de exercício) (fração).",
    },
    {
        "sk_indicador": 25,
        "codigo": "LIQUIDEZ_CORRENTE",
        "nome": "Liquidez Corrente",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "Razão",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Ativo Circulante / Passivo Circulante.",
    },
    {
        "sk_indicador": 26,
        "codigo": "DIVIDA_BRUTA",
        "nome": "Dívida Bruta",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Empréstimos e Financiamentos CP + LP.",
    },
    {
        "sk_indicador": 27,
        "codigo": "DIVIDA_LIQUIDA",
        "nome": "Dívida Líquida",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "R$",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Dívida Bruta - (Caixa e Equivalentes + Aplicações Financeiras).",
    },
    {
        "sk_indicador": 28,
        "codigo": "CRESC_RECEITA",
        "nome": "Crescimento de Receita (YoY)",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "fração",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "(Receita Líquida t / Receita Líquida t-1) - 1.",
    },
    {
        "sk_indicador": 29,
        "codigo": "RETORNO_DIARIO",
        "nome": "Retorno Diário",
        "fonte": "B3",
        "tipo": "derivado",
        "unidade": "fração",
        "granularidade": "diária",
        "agg_mensal": "soma",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "(Close_t / Close_t-1) - 1.",
    },
    {
        "sk_indicador": 30,
        "codigo": "SMA_21",
        "nome": "Média Móvel Simples 21D",
        "fonte": "B3",
        "tipo": "derivado",
        "unidade": "R$",
        "granularidade": "diária",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Média móvel simples do preço de fechamento ajustado de 21 dias.",
    },
    {
        "sk_indicador": 31,
        "codigo": "SMA_50",
        "nome": "Média Móvel Simples 50D",
        "fonte": "B3",
        "tipo": "derivado",
        "unidade": "R$",
        "granularidade": "diária",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Média móvel simples do preço de fechamento ajustado de 50 dias.",
    },
    {
        "sk_indicador": 32,
        "codigo": "VOLUME_FIN_APROX",
        "nome": "Volume Financeiro Aproximado",
        "fonte": "B3",
        "tipo": "derivado",
        "unidade": "R$",
        "granularidade": "diária",
        "agg_mensal": "soma",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Close ajustado * Volume em quantidade de ações.",
    },
]


def dicionario_markdown() -> str:
    """Gera documentação em formato Markdown do Dicionário de Dados da camada Ouro."""
    lines = []
    lines.append("## 5. Dicionário de Dados (Camada Ouro)")
    lines.append("")

    # dim_tempo
    lines.append("### `dim_tempo` (Dimensão de Tempo)")
    lines.append("| Coluna | Tipo | Descrição / Regra de Negócio |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| `sk_tempo` | `INTEGER` | Chave primária substituta no formato YYYYMMDD. |")
    lines.append("| `data` | `DATE` | Data calendário. |")
    lines.append("| `ano` | `INTEGER` | Ano de referência (ex: 2023). |")
    lines.append("| `semestre` | `INTEGER` | Semestre do ano (1 ou 2). |")
    lines.append("| `trimestre` | `INTEGER` | Trimestre do ano (1 a 4). |")
    lines.append("| `mes` | `INTEGER` | Mês do ano (1 a 12). |")
    lines.append("| `ano_mes` | `VARCHAR` | Formato 'YYYY-MM' para agregação mensal. |")
    lines.append("| `dia_util_b3` | `BOOLEAN` | Flag indicando se houve pregão na B3. |")
    lines.append("")

    # dim_empresa
    lines.append("### `dim_empresa` (Dimensão de Empresas)")
    lines.append("| Coluna | Tipo | Descrição / Regra de Negócio |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| `sk_empresa` | `INTEGER` | Chave substituta (código CVM da empresa). |")
    lines.append("| `ticker` | `VARCHAR` | Código do ativo negociado na B3 (ex: WEGE3, ITUB4). |")
    lines.append("| `cd_cvm` | `INTEGER` | Código de registro da empresa na CVM. |")
    lines.append("| `cnpj` | `VARCHAR` | CNPJ da empresa. |")
    lines.append("| `denom_cia` | `VARCHAR` | Razão social / Denominação social oficial. |")
    lines.append("| `setor_cvm` | `VARCHAR` | Setor de atividade cadastrado na CVM. |")
    lines.append("| `setor_analitico` | `VARCHAR` | Setor analítico unificado do projeto. |")
    lines.append("| `tipo_plano` | `VARCHAR` | Tipo de plano contábil ('industrial' ou 'financeira'). |")
    lines.append("| `exportadora_commodities` | `BOOLEAN` | Flag de empresa exportadora de commodities. |")
    lines.append("| `tem_cvm` | `BOOLEAN` | Flag indicando presença de dados na CVM. |")
    lines.append("| `tem_b3` | `BOOLEAN` | Flag indicando presença de cotações na B3. |")
    lines.append("")

    # dim_indicador
    lines.append("### `dim_indicador` (Dimensão de Indicadores)")
    lines.append("| Coluna | Tipo | Descrição / Regra de Negócio |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| `sk_indicador` | `INTEGER` | Chave primária substituta do indicador. |")
    lines.append("| `codigo` | `VARCHAR` | Código textual único do indicador (ex: SELIC_META, ROE). |")
    lines.append("| `nome` | `VARCHAR` | Nome descritivo completo. |")
    lines.append("| `fonte` | `VARCHAR` | Origem da informação ('BACEN', 'CVM', 'B3'). |")
    lines.append("| `tipo` | `VARCHAR` | Tipo do indicador ('bruto' ou 'derivado'). |")
    lines.append("| `unidade` | `VARCHAR` | Unidade de medida ('R$', 'fração', '% a.a.', '%', 'Razão', 'Índice'). |")
    lines.append("| `granularidade` | `VARCHAR` | Frequência nativa ('diária', 'mensal', 'anual'). |")
    lines.append("| `agg_mensal` | `VARCHAR` | Regra de agregação para escala mensal ('ultimo', 'soma', 'media'). |")
    lines.append("| `sgs_codigo` | `INTEGER` | Código da série temporal no SGS/BACEN (se aplicável). |")
    lines.append("| `cd_conta` | `VARCHAR` | Código da conta contábil DRE/BPA/BPP na CVM (se aplicável). |")
    lines.append("| `regra_calculo` | `VARCHAR` | Fórmula ou regra de cálculo do indicador. |")
    lines.append("")

    # Catálogo de Indicadores
    lines.append("#### Catálogo de Indicadores do Projeto")
    lines.append("| SK | Código | Nome | Fonte | Tipo | Unidade | Regra de Cálculo / Fórmula |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for ind in INDICADOR_SEED:
        lines.append(
            f"| {ind['sk_indicador']} | `{ind['codigo']}` | {ind['nome']} | {ind['fonte']} | {ind['tipo']} | {ind['unidade']} | {ind['regra_calculo']} |"
        )
    lines.append("")

    # fato_macro
    lines.append("### `fato_macro` (Fato Macroeconômica)")
    lines.append("| Coluna | Tipo | Descrição / Regra de Negócio |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| `sk_tempo` | `INTEGER` | Chave estrangeira para `dim_tempo`. |")
    lines.append("| `sk_indicador` | `INTEGER` | Chave estrangeira para `dim_indicador`. |")
    lines.append("| `valor` | `NUMERIC` | Valor observado da série macroeconômica na data nativa. |")
    lines.append("")

    # fato_cotacoes
    lines.append("### `fato_cotacoes` (Fato Mercado e Cotações)")
    lines.append("| Coluna | Tipo | Descrição / Regra de Negócio |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| `sk_tempo` | `INTEGER` | Chave estrangeira para `dim_tempo`. |")
    lines.append("| `sk_empresa` | `INTEGER` | Chave estrangeira para `dim_empresa`. |")
    lines.append("| `open` | `NUMERIC` | Preço de abertura da ação no pregão (R$). |")
    lines.append("| `high` | `NUMERIC` | Preço máximo negociado no pregão (R$). |")
    lines.append("| `low` | `NUMERIC` | Preço mínimo negociado no pregão (R$). |")
    lines.append("| `close` | `NUMERIC` | Preço de fechamento ajustado por proventos (R$). |")
    lines.append("| `volume` | `NUMERIC` | Volume em quantidade de títulos negociados. |")
    lines.append("| `volume_fin_aprox` | `NUMERIC` | Volume financeiro aproximado em R$ (`close × volume`). |")
    lines.append("| `retorno_diario` | `NUMERIC` | Retorno diário percentual em fração (`close_t / close_t-1 - 1`). |")
    lines.append("| `sma_21` | `NUMERIC` | Média móvel simples de 21 pregões (R$). |")
    lines.append("| `sma_50` | `NUMERIC` | Média móvel simples de 50 pregões (R$). |")
    lines.append("")

    # fato_demonstrativos
    lines.append("### `fato_demonstrativos` (Fato Demonstrativos Financeiros CVM)")
    lines.append("| Coluna | Tipo | Descrição / Regra de Negócio |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| `sk_tempo` | `INTEGER` | Chave estrangeira para `dim_tempo` (data `DT_FIM_EXERC`). |")
    lines.append("| `sk_empresa` | `INTEGER` | Chave estrangeira para `dim_empresa`. |")
    lines.append("| `sk_indicador` | `INTEGER` | Chave estrangeira para `dim_indicador`. |")
    lines.append("| `valor` | `NUMERIC` | Valor em R$ ou razão em fração referente ao exercício anual. |")
    lines.append("")

    return "\n".join(lines)


class StarSchemaBuilder:
    """Orquestrador de criação e atualização das dimensões e fatos do Star Schema."""

    def __init__(
        self,
        logger: Optional[PipelineLogger] = None,
        persistence: Optional[Persistence] = None,
    ) -> None:
        self.logger = logger or PipelineLogger()
        self.persistence = persistence or Persistence()

    def _build_dim_tempo(self, params: PipelineParams) -> pd.DataFrame:
        """Gera dim_tempo diária cobrindo de 2020-12-31 até o maior período selecionado."""
        modo = params.modo

        min_date_str = min("2020-12-31", params.bacen_periodo[0], params.b3_periodo[0])
        max_date_str = max(params.bacen_periodo[1], params.b3_periodo[1])

        if params.cvm_anos:
            max_cvm_year = max(params.cvm_anos)
            cvm_end = f"{max_cvm_year}-12-31"
            if cvm_end > max_date_str:
                max_date_str = cvm_end

        df_b3 = self.persistence.load("silver", "b3_cotacoes", columns=["data"], modo=modo)
        b3_dates = set()
        if not df_b3.empty and "data" in df_b3.columns:
            b3_dates = set(pd.to_datetime(df_b3["data"]).dt.date)

        date_range = pd.date_range(start=min_date_str, end=max_date_str, freq="D")

        dim_tempo_data = []
        for dt in date_range:
            d_date = dt.date()
            sk_tempo = int(dt.strftime("%Y%m%d"))
            ano = dt.year
            mes = dt.month
            semestre = 1 if mes <= 6 else 2
            trimestre = (mes - 1) // 3 + 1
            ano_mes = dt.strftime("%Y-%m")
            dia_util_b3 = d_date in b3_dates if len(b3_dates) > 0 else False

            dim_tempo_data.append(
                {
                    "sk_tempo": sk_tempo,
                    "data": d_date,
                    "ano": ano,
                    "semestre": semestre,
                    "trimestre": trimestre,
                    "mes": mes,
                    "ano_mes": ano_mes,
                    "dia_util_b3": dia_util_b3,
                }
            )

        return pd.DataFrame(dim_tempo_data)

    def _build_dim_empresa(self, params: PipelineParams) -> pd.DataFrame:
        """Gera dim_empresa a partir do universo configurado enriquecido com cadastro CVM e presenças."""
        modo = params.modo

        df_cad = self.persistence.load("silver", "cvm_cadastro", modo=modo)
        df_cvm = self.persistence.load("silver", "cvm_demonstrativos", columns=["cd_cvm"], modo=modo)
        df_b3 = self.persistence.load("silver", "b3_cotacoes", columns=["ticker"], modo=modo)

        cvm_presentes = set(df_cvm["cd_cvm"].unique()) if not df_cvm.empty else set()
        b3_presentes = set(df_b3["ticker"].unique()) if not df_b3.empty else set()

        cad_map = {}
        if not df_cad.empty:
            for _, row in df_cad.iterrows():
                cad_map[int(row["cd_cvm"])] = {
                    "cnpj": str(row.get("cnpj", "")),
                    "denom_cia": str(row.get("denom_cia", "")),
                    "setor_cvm": str(row.get("setor_cvm", "Não informado")),
                }

        dim_empresa_data = []
        warnings = []

        for ticker in params.tickers:
            if ticker not in universe.COMPANIES:
                warnings.append(f"Ticker '{ticker}' não localizado em universe.COMPANIES")
                continue

            info = universe.COMPANIES[ticker]
            cd_cvm = info.cd_cvm
            cad_info = cad_map.get(cd_cvm, {})

            if not cad_info and not df_cad.empty:
                warnings.append(f"Empresa '{ticker}' (CD_CVM {cd_cvm}) sem cadastro na Prata cvm_cadastro")

            cnpj = cad_info.get("cnpj") or ""
            denom_cia = cad_info.get("denom_cia") or info.denom_cia
            setor_cvm = cad_info.get("setor_cvm") or "Não informado"

            tem_cvm = cd_cvm in cvm_presentes
            tem_b3 = ticker in b3_presentes

            dim_empresa_data.append(
                {
                    "sk_empresa": cd_cvm,
                    "ticker": ticker,
                    "cd_cvm": cd_cvm,
                    "cnpj": cnpj,
                    "denom_cia": denom_cia,
                    "setor_cvm": setor_cvm,
                    "setor_analitico": info.setor_analitico,
                    "tipo_plano": info.tipo_plano,
                    "exportadora_commodities": info.exportadora_commodities,
                    "tem_cvm": tem_cvm,
                    "tem_b3": tem_b3,
                }
            )

        df_result = pd.DataFrame(dim_empresa_data)
        df_result.attrs["warnings"] = warnings
        return df_result

    def _build_dim_indicador(self) -> pd.DataFrame:
        """Gera dim_indicador a partir da seed estática pré-configurada."""
        return pd.DataFrame(INDICADOR_SEED)

    def run_dims(self, params: PipelineParams) -> StepResult:
        """Executa a construção e gravação das 3 dimensões da Ouro."""
        start_time = time.time()
        step_id = "run_dims"
        self.logger.emit("INFO", "StarSchemaBuilder", "START", f"Iniciando construção de dimensões ({params.modo})")

        try:
            df_tempo = self._build_dim_tempo(params)
            df_empresa = self._build_dim_empresa(params)
            df_indicador = self._build_dim_indicador()

            warnings = list(df_empresa.attrs.get("warnings", []))

            res_tempo = self.persistence.save("gold", "dim_tempo", df_tempo, modo=params.modo)
            res_empresa = self.persistence.save("gold", "dim_empresa", df_empresa, modo=params.modo)
            res_indicador = self.persistence.save("gold", "dim_indicador", df_indicador, modo=params.modo)

            paths_saved = [
                res_tempo.get("parquet_path", ""),
                res_empresa.get("parquet_path", ""),
                res_indicador.get("parquet_path", ""),
            ]
            total_rows = len(df_tempo) + len(df_empresa) + len(df_indicador)

            duration = time.time() - start_time
            self.logger.emit(
                "INFO",
                "StarSchemaBuilder",
                "END",
                f"Dimensões criadas: tempo={len(df_tempo)}, empresa={len(df_empresa)}, indicador={len(df_indicador)}",
            )

            return StepResult(
                step_id=step_id,
                ok=True,
                rows=total_rows,
                paths=[p for p in paths_saved if p],
                duration_s=duration,
                warnings=warnings,
            )

        except Exception as e:
            duration = time.time() - start_time
            err_msg = str(e)
            self.logger.emit("ERROR", "StarSchemaBuilder", "FAILURE", f"Falha ao criar dimensões: {err_msg}")
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                duration_s=duration,
                error=err_msg,
            )
        finally:
            release()

    def _ensure_dims_exist(self, modo: str) -> bool:
        """Garante que as dimensões da Ouro existem antes de popular fatos."""
        df_tempo = self.persistence.load("gold", "dim_tempo", modo=modo)
        df_empresa = self.persistence.load("gold", "dim_empresa", modo=modo)
        df_indicador = self.persistence.load("gold", "dim_indicador", modo=modo)

        return not df_tempo.empty and not df_empresa.empty and not df_indicador.empty

    def _update_dim_empresa_flags(self, source: str, params: PipelineParams) -> None:
        """Atualiza unicamente as flags tem_b3 e tem_cvm na dim_empresa sem alterar chaves."""
        df_empresa = self.persistence.load("gold", "dim_empresa", modo=params.modo)
        if df_empresa.empty:
            return

        if source == "b3":
            df_b3 = self.persistence.load("silver", "b3_cotacoes", columns=["ticker"], modo=params.modo)
            b3_presentes = set(df_b3["ticker"].unique()) if not df_b3.empty else set()
            df_empresa["tem_b3"] = df_empresa["ticker"].isin(b3_presentes)
        elif source == "cvm":
            df_cvm = self.persistence.load("silver", "cvm_demonstrativos", columns=["cd_cvm"], modo=params.modo)
            cvm_presentes = set(df_cvm["cd_cvm"].unique()) if not df_cvm.empty else set()
            df_empresa["tem_cvm"] = df_empresa["cd_cvm"].isin(cvm_presentes)

        self.persistence.save("gold", "dim_empresa", df_empresa, modo=params.modo)

    def _build_fato_macro(self, params: PipelineParams) -> Tuple[pd.DataFrame, List[str]]:
        """Gera fato_macro a partir de silver.bacen_sgs e calcula JURO_REAL_EXPOST por Fisher."""
        modo = params.modo
        warnings = []

        df_bacen = self.persistence.load("silver", "bacen_sgs", modo=modo)
        if df_bacen.empty:
            warnings.append("Prata silver.bacen_sgs vazia.")
            return pd.DataFrame(columns=["sk_tempo", "sk_indicador", "valor"]), warnings

        sgs_col = "serie_codigo" if "serie_codigo" in df_bacen.columns else "sgs_codigo"
        if sgs_col not in df_bacen.columns:
            sgs_col = next((c for c in ["codigo_sgs", "codigo"] if c in df_bacen.columns), None)

        if not sgs_col or "data" not in df_bacen.columns:
            warnings.append("Colunas necessárias não encontradas na Prata silver.bacen_sgs.")
            return pd.DataFrame(columns=["sk_tempo", "sk_indicador", "valor"]), warnings

        df_indicador = self.persistence.load("gold", "dim_indicador", modo=modo)
        bacen_ind = df_indicador[df_indicador["fonte"] == "BACEN"]
        sgs_map = {}
        for _, row in bacen_ind.dropna(subset=["sgs_codigo"]).iterrows():
            sgs_map[int(row["sgs_codigo"])] = int(row["sk_indicador"])

        df_bacen["_sgs_int"] = pd.to_numeric(df_bacen[sgs_col], errors="coerce").fillna(-1).astype(int)
        df_bacen["data_dt"] = pd.to_datetime(df_bacen["data"])
        df_bacen["sk_tempo"] = df_bacen["data_dt"].dt.strftime("%Y%m%d").astype(int)
        df_bacen["valor"] = pd.to_numeric(df_bacen["valor"], errors="coerce")

        fatos_brutos = []
        for sgs_code, sk_ind in sgs_map.items():
            sub_df = df_bacen[df_bacen["_sgs_int"] == int(sgs_code)].copy()
            if sub_df.empty:
                continue
            sub_df["sk_indicador"] = sk_ind
            fatos_brutos.append(sub_df[["sk_tempo", "sk_indicador", "valor"]])

        df_fatos = pd.concat(fatos_brutos, ignore_index=True) if fatos_brutos else pd.DataFrame()

        selic_meta_df = df_bacen[df_bacen["_sgs_int"] == 432].copy()
        ipca_12m_df = df_bacen[df_bacen["_sgs_int"] == 13522].copy()

        fatos_juro_real = []
        if not selic_meta_df.empty and not ipca_12m_df.empty:
            selic_meta_df["ano_mes"] = selic_meta_df["data_dt"].dt.strftime("%Y-%m")
            selic_monthly = selic_meta_df.sort_values("data_dt").groupby("ano_mes").last().reset_index()

            ipca_12m_df["ano_mes"] = ipca_12m_df["data_dt"].dt.strftime("%Y-%m")
            ipca_monthly = ipca_12m_df.groupby("ano_mes").last().reset_index()

            merged = pd.merge(
                selic_monthly[["ano_mes", "valor"]],
                ipca_monthly[["ano_mes", "valor"]],
                on="ano_mes",
                suffixes=("_selic", "_ipca"),
            )

            for _, row in merged.iterrows():
                ano_mes = str(row["ano_mes"])
                dt_day1 = pd.to_datetime(f"{ano_mes}-01")
                sk_tempo = int(dt_day1.strftime("%Y%m%d"))

                val_fisher = juro_real_fisher(row["valor_selic"], row["valor_ipca"])
                if not pd.isna(val_fisher):
                    fatos_juro_real.append(
                        {
                            "sk_tempo": sk_tempo,
                            "sk_indicador": 8,
                            "valor": float(val_fisher),
                        }
                    )

        if fatos_juro_real:
            df_juro_real = pd.DataFrame(fatos_juro_real)
            df_fatos = pd.concat([df_fatos, df_juro_real], ignore_index=True)

        return df_fatos, warnings

    def _build_fato_demonstrativos(self, params: PipelineParams) -> Tuple[pd.DataFrame, List[str]]:
        """Gera fato_demonstrativos a partir de silver.cvm_demonstrativos e calcula métricas fundamentalistas."""
        modo = params.modo
        warnings = []

        df_cvm = self.persistence.load("silver", "cvm_demonstrativos", modo=modo)
        if df_cvm.empty:
            warnings.append("Prata silver.cvm_demonstrativos vazia.")
            return pd.DataFrame(), warnings

        if "versao" in df_cvm.columns:
            df_cvm["versao_num"] = pd.to_numeric(df_cvm["versao"], errors="coerce").fillna(1).astype(int)
            df_cvm = df_cvm.sort_values("versao_num")

        dedup_keys = [c for c in ["cd_cvm", "dt_fim_exerc", "demonstrativo", "cd_conta"] if c in df_cvm.columns]
        if dedup_keys:
            df_cvm = df_cvm.groupby(dedup_keys, as_index=False).last()

        df_empresa = self.persistence.load("gold", "dim_empresa", modo=modo)
        emp_map = {}
        for _, row in df_empresa.iterrows():
            emp_map[int(row["cd_cvm"])] = {
                "sk_empresa": int(row["sk_empresa"]),
                "tipo_plano": str(row["tipo_plano"]),
            }

        df_indicador = self.persistence.load("gold", "dim_indicador", modo=modo)
        cvm_ind = df_indicador[df_indicador["fonte"] == "CVM"]
        key_to_sk = dict(zip(cvm_ind["codigo"], cvm_ind["sk_indicador"]))

        cd_cvm_col = "cd_cvm" if "cd_cvm" in df_cvm.columns else "CD_CVM"
        dt_fim_col = "dt_fim_exerc" if "dt_fim_exerc" in df_cvm.columns else "DT_FIM_EXERC"

        df_cvm["_cd_cvm_int"] = pd.to_numeric(df_cvm[cd_cvm_col], errors="coerce").fillna(0).astype(int)
        is_long = "cd_conta" in df_cvm.columns and "vl_conta" in df_cvm.columns

        fatos_cvm = []

        for cd_cvm, group in df_cvm.groupby("_cd_cvm_int"):
            cd_cvm_int = int(cd_cvm)
            if cd_cvm_int not in emp_map:
                warnings.append(f"CD_CVM '{cd_cvm}' não localizado em dim_empresa; descartando.")
                continue

            sk_empresa = emp_map[cd_cvm_int]["sk_empresa"]
            tipo_plano = emp_map[cd_cvm_int]["tipo_plano"]

            group_sorted = group.sort_values(dt_fim_col).copy()
            years_data = {}

            if is_long:
                group_sorted["vl_conta"] = pd.to_numeric(group_sorted["vl_conta"], errors="coerce")
                for dt_fim_val, sub_grp in group_sorted.groupby(dt_fim_col):
                    dt_fim = pd.to_datetime(dt_fim_val)
                    sk_tempo = int(dt_fim.strftime("%Y%m%d"))
                    ano = dt_fim.year

                    sub_grp_clean = sub_grp.copy()
                    sub_grp_clean["cd_conta_str"] = sub_grp_clean["cd_conta"].astype(str).str.strip()
                    conta_map = dict(zip(sub_grp_clean["cd_conta_str"], sub_grp_clean["vl_conta"]))

                    ind_code_map = {}
                    if "codigo_indicador" in sub_grp_clean.columns:
                        valid_ind = sub_grp_clean.dropna(subset=["codigo_indicador"])
                        ind_code_map = dict(
                            zip(
                                valid_ind["codigo_indicador"].astype(str).str.strip(),
                                valid_ind["vl_conta"],
                            )
                        )

                    def _get_val_m(ind_key: str, conta_codes: List[str]) -> float:
                        if ind_key in ind_code_map and not pd.isna(ind_code_map[ind_key]):
                            return float(ind_code_map[ind_key])
                        for code in conta_codes:
                            if code in conta_map and not pd.isna(conta_map[code]):
                                return float(conta_map[code])
                        return np.nan

                    yr_entry = {
                        "sk_tempo": sk_tempo,
                        "RECEITA_LIQUIDA": _get_val_m("RECEITA_LIQUIDA", ["3.01", "3.01.01"]),
                        "LUCRO_BRUTO": _get_val_m("LUCRO_BRUTO", ["3.03"]),
                        "EBIT": _get_val_m("EBIT", ["3.05"]),
                        "DESP_FINANCEIRAS": _get_val_m("DESP_FINANCEIRAS", ["3.06.02", "3.06"]),
                        "LUCRO_LIQUIDO": _get_val_m("LUCRO_LIQUIDO", ["3.11", "3.09", "3.07"]),
                        "ATIVO_CIRCULANTE": _get_val_m("ATIVO_CIRCULANTE", ["1.01"]),
                        "PASSIVO_CIRCULANTE": _get_val_m("PASSIVO_CIRCULANTE", ["2.01"]),
                        "CAIXA_EQUIV": _get_val_m("CAIXA_EQUIV", ["1.01.01"]),
                        "APLIC_FINANC": _get_val_m("APLIC_FINANC", ["1.01.02"]),
                        "EMPR_FIN_CP": _get_val_m("EMPR_FIN_CP", ["2.01.04"]),
                        "EMPR_FIN_LP": _get_val_m("EMPR_FIN_LP", ["2.02.01"]),
                        "PATRIMONIO_LIQUIDO": _get_val_m("PATRIMONIO_LIQUIDO", ["2.03"]),
                        "RECEITA_INTERMEDIACAO": _get_val_m("RECEITA_INTERMEDIACAO", ["3.01"]),
                    }
                    years_data[ano] = yr_entry
            else:
                col_map_lower = {str(c).lower(): c for c in df_cvm.columns}

                def _get_val(r: pd.Series, key: str) -> Any:
                    actual_col = col_map_lower.get(key.lower())
                    if actual_col and actual_col in r:
                        v = r[actual_col]
                        return pd.to_numeric(v, errors="coerce") if not pd.isna(v) else np.nan
                    return np.nan

                for _, row in group_sorted.iterrows():
                    dt_fim = pd.to_datetime(row[dt_fim_col])
                    sk_tempo = int(dt_fim.strftime("%Y%m%d"))
                    ano = dt_fim.year

                    yr_entry = {
                        "sk_tempo": sk_tempo,
                        "RECEITA_LIQUIDA": _get_val(row, "RECEITA_LIQUIDA"),
                        "LUCRO_BRUTO": _get_val(row, "LUCRO_BRUTO"),
                        "EBIT": _get_val(row, "EBIT"),
                        "DESP_FINANCEIRAS": _get_val(row, "DESP_FINANCEIRAS"),
                        "LUCRO_LIQUIDO": _get_val(row, "LUCRO_LIQUIDO"),
                        "ATIVO_CIRCULANTE": _get_val(row, "ATIVO_CIRCULANTE"),
                        "PASSIVO_CIRCULANTE": _get_val(row, "PASSIVO_CIRCULANTE"),
                        "CAIXA_EQUIV": _get_val(row, "CAIXA_EQUIV"),
                        "APLIC_FINANC": _get_val(row, "APLIC_FINANC"),
                        "EMPR_FIN_CP": _get_val(row, "EMPR_FIN_CP"),
                        "EMPR_FIN_LP": _get_val(row, "EMPR_FIN_LP"),
                        "PATRIMONIO_LIQUIDO": _get_val(row, "PATRIMONIO_LIQUIDO"),
                        "RECEITA_INTERMEDIACAO": _get_val(row, "RECEITA_INTERMEDIACAO"),
                    }
                    years_data[ano] = yr_entry

            sorted_years = sorted(years_data.keys())
            rl_series = pd.Series(
                [years_data[yr]["RECEITA_LIQUIDA"] for yr in sorted_years],
                index=sorted_years,
            )
            cresc_series = crescimento(rl_series)

            for i, yr in enumerate(sorted_years):
                data = years_data[yr]
                sk_tempo = data["sk_tempo"]

                if tipo_plano == "industrial":
                    for key in [
                        "RECEITA_LIQUIDA",
                        "LUCRO_BRUTO",
                        "EBIT",
                        "DESP_FINANCEIRAS",
                        "LUCRO_LIQUIDO",
                        "ATIVO_CIRCULANTE",
                        "PASSIVO_CIRCULANTE",
                        "CAIXA_EQUIV",
                        "APLIC_FINANC",
                        "EMPR_FIN_CP",
                        "EMPR_FIN_LP",
                        "PATRIMONIO_LIQUIDO",
                    ]:
                        val = data[key]
                        if not pd.isna(val) and key in key_to_sk:
                            fatos_cvm.append(
                                {
                                    "sk_tempo": sk_tempo,
                                    "sk_empresa": sk_empresa,
                                    "sk_indicador": key_to_sk[key],
                                    "valor": float(val),
                                }
                            )

                    ml = margem_liquida(data["LUCRO_LIQUIDO"], data["RECEITA_LIQUIDA"])
                    if not pd.isna(ml):
                        fatos_cvm.append(
                            {
                                "sk_tempo": sk_tempo,
                                "sk_empresa": sk_empresa,
                                "sk_indicador": key_to_sk["MARGEM_LIQUIDA"],
                                "valor": float(ml),
                            }
                        )

                    me = margem_ebit(data["EBIT"], data["RECEITA_LIQUIDA"])
                    if not pd.isna(me):
                        fatos_cvm.append(
                            {
                                "sk_tempo": sk_tempo,
                                "sk_empresa": sk_empresa,
                                "sk_indicador": key_to_sk["MARGEM_EBIT"],
                                "valor": float(me),
                            }
                        )

                    r_oe = roe(data["LUCRO_LIQUIDO"], data["PATRIMONIO_LIQUIDO"])
                    if not pd.isna(r_oe):
                        fatos_cvm.append(
                            {
                                "sk_tempo": sk_tempo,
                                "sk_empresa": sk_empresa,
                                "sk_indicador": key_to_sk["ROE"],
                                "valor": float(r_oe),
                            }
                        )

                    lc = liquidez_corrente(data["ATIVO_CIRCULANTE"], data["PASSIVO_CIRCULANTE"])
                    if not pd.isna(lc):
                        fatos_cvm.append(
                            {
                                "sk_tempo": sk_tempo,
                                "sk_empresa": sk_empresa,
                                "sk_indicador": key_to_sk["LIQUIDEZ_CORRENTE"],
                                "valor": float(lc),
                            }
                        )

                    db_val = divida_bruta(data["EMPR_FIN_CP"], data["EMPR_FIN_LP"])
                    if not pd.isna(db_val):
                        fatos_cvm.append(
                            {
                                "sk_tempo": sk_tempo,
                                "sk_empresa": sk_empresa,
                                "sk_indicador": key_to_sk["DIVIDA_BRUTA"],
                                "valor": float(db_val),
                            }
                        )

                    dl_val = divida_liquida(
                        data["EMPR_FIN_CP"],
                        data["EMPR_FIN_LP"],
                        data["CAIXA_EQUIV"],
                        data["APLIC_FINANC"],
                    )
                    if not pd.isna(dl_val):
                        fatos_cvm.append(
                            {
                                "sk_tempo": sk_tempo,
                                "sk_empresa": sk_empresa,
                                "sk_indicador": key_to_sk["DIVIDA_LIQUIDA"],
                                "valor": float(dl_val),
                            }
                        )

                    cresc_val = cresc_series.iloc[i]
                    if not pd.isna(cresc_val):
                        fatos_cvm.append(
                            {
                                "sk_tempo": sk_tempo,
                                "sk_empresa": sk_empresa,
                                "sk_indicador": key_to_sk["CRESC_RECEITA"],
                                "valor": float(cresc_val),
                            }
                        )

                elif tipo_plano == "financeira":
                    for key in ["LUCRO_LIQUIDO", "PATRIMONIO_LIQUIDO", "RECEITA_INTERMEDIACAO"]:
                        val = data[key]
                        if not pd.isna(val) and key in key_to_sk:
                            fatos_cvm.append(
                                {
                                    "sk_tempo": sk_tempo,
                                    "sk_empresa": sk_empresa,
                                    "sk_indicador": key_to_sk[key],
                                    "valor": float(val),
                                }
                            )

                    r_oe = roe(data["LUCRO_LIQUIDO"], data["PATRIMONIO_LIQUIDO"])
                    if not pd.isna(r_oe):
                        fatos_cvm.append(
                            {
                                "sk_tempo": sk_tempo,
                                "sk_empresa": sk_empresa,
                                "sk_indicador": key_to_sk["ROE"],
                                "valor": float(r_oe),
                            }
                        )

        df_result = pd.DataFrame(fatos_cvm) if fatos_cvm else pd.DataFrame()
        return df_result, warnings

    def _build_fato_cotacoes(self, params: PipelineParams) -> Tuple[pd.DataFrame, List[str]]:
        """Gera fato_cotacoes a partir de silver.b3_cotacoes calculando indicadores de mercado."""
        modo = params.modo
        warnings = []

        df_b3 = self.persistence.load("silver", "b3_cotacoes", modo=modo)
        if df_b3.empty:
            warnings.append("Prata silver.b3_cotacoes vazia.")
            return pd.DataFrame(), warnings

        df_empresa = self.persistence.load("gold", "dim_empresa", modo=modo)
        ticker_map = dict(zip(df_empresa["ticker"], df_empresa["sk_empresa"]))

        fatos_b3 = []
        df_b3["data_dt"] = pd.to_datetime(df_b3["data"])

        for ticker, group in df_b3.groupby("ticker"):
            if ticker not in ticker_map:
                warnings.append(f"Ticker '{ticker}' em B3 não localizado em dim_empresa; descartando.")
                continue

            sk_empresa = ticker_map[ticker]
            grp_sorted = group.sort_values("data_dt").copy()

            close_s = grp_sorted["close"]
            grp_sorted["retorno_diario"] = retorno_diario(close_s)
            grp_sorted["sma_21"] = sma(close_s, 21)
            grp_sorted["sma_50"] = sma(close_s, 50)
            grp_sorted["volume_fin_aprox"] = grp_sorted["close"] * grp_sorted["volume"]
            grp_sorted["sk_tempo"] = grp_sorted["data_dt"].dt.strftime("%Y%m%d").astype(int)
            grp_sorted["sk_empresa"] = sk_empresa

            cols = [
                "sk_tempo",
                "sk_empresa",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "volume_fin_aprox",
                "retorno_diario",
                "sma_21",
                "sma_50",
            ]
            fatos_b3.append(grp_sorted[cols])

        df_result = pd.concat(fatos_b3, ignore_index=True) if fatos_b3 else pd.DataFrame()
        return df_result, warnings

    def run_gold(self, source: str, params: PipelineParams) -> StepResult:
        """Executa a construção e gravação dos fatos da Ouro para a fonte especificada."""
        start_time = time.time()
        source_lower = source.lower()
        step_id = f"run_gold_{source_lower}"

        self.logger.emit("INFO", "StarSchemaBuilder", "START", f"Iniciando run_gold('{source_lower}') ({params.modo})")

        if not self._ensure_dims_exist(params.modo):
            err_msg = "Dimensões do Star Schema ausentes na Ouro. Execute 'run_dims' antes de chamar 'run_gold'."
            self.logger.emit("ERROR", "StarSchemaBuilder", "FAILURE", err_msg)
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], duration_s=0.0, error=err_msg)

        try:
            if source_lower == "bacen":
                df_fato, warnings = self._build_fato_macro(params)
                nome_tabela = "fato_macro"
                partition_cols = ["sk_indicador"]
            elif source_lower == "b3":
                df_fato, warnings = self._build_fato_cotacoes(params)
                nome_tabela = "fato_cotacoes"
                partition_cols = ["sk_empresa"]
            elif source_lower == "cvm":
                df_fato, warnings = self._build_fato_demonstrativos(params)
                nome_tabela = "fato_demonstrativos"
                partition_cols = ["sk_empresa"]
            else:
                raise ValueError(f"Fonte Ouro desconhecida: '{source}'. Esperadas: 'bacen', 'b3', 'cvm'")

            rows_count = len(df_fato)
            res = self.persistence.save("gold", nome_tabela, df_fato, partition_cols=partition_cols, modo=params.modo)

            if source_lower in {"b3", "cvm"}:
                self._update_dim_empresa_flags(source_lower, params)

            duration = time.time() - start_time
            self.logger.emit(
                "INFO",
                "StarSchemaBuilder",
                "END",
                f"Tabela {nome_tabela} atualizada com {rows_count} linhas em {duration:.2f}s",
            )

            return StepResult(
                step_id=step_id,
                ok=True,
                rows=rows_count,
                paths=[res.get("parquet_path", "")],
                duration_s=duration,
                warnings=warnings,
            )

        except Exception as e:
            duration = time.time() - start_time
            err_msg = str(e)
            self.logger.emit("ERROR", "StarSchemaBuilder", "FAILURE", f"Falha no run_gold('{source_lower}'): {err_msg}")
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                duration_s=duration,
                error=err_msg,
            )
        finally:
            release()