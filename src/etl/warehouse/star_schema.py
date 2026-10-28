"""Construção e gestão das dimensões e fatos da camada Ouro (Star Schema)."""

import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.config import accounts, settings, universe
from src.etl.base import PipelineLogger
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


# ------------------------------------------------------------------------------
# Seed de dim_indicador (BACEN, CVM e B3)
# ------------------------------------------------------------------------------
INDICADOR_SEED: List[Dict[str, Any]] = [
    # BACEN Bruto
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
    # BACEN Derivado
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
    # CVM Bruto
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
    # CVM Derivado
    {
        "sk_indicador": 22,
        "codigo": "MARGEM_LIQUIDA",
        "nome": "Margem Líquida",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "%",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Lucro Líquido / Receita Líquida * 100.",
    },
    {
        "sk_indicador": 23,
        "codigo": "MARGEM_EBIT",
        "nome": "Margem EBIT",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "%",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "EBIT / Receita Líquida * 100.",
    },
    {
        "sk_indicador": 24,
        "codigo": "ROE",
        "nome": "Return on Equity (ROE)",
        "fonte": "CVM",
        "tipo": "derivado",
        "unidade": "%",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "Lucro Líquido / Patrimônio Líquido (fim de exercício) * 100.",
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
        "unidade": "%",
        "granularidade": "anual",
        "agg_mensal": "ultimo",
        "sgs_codigo": None,
        "cd_conta": None,
        "regra_calculo": "(Receita Líquida t / Receita Líquida t-1) - 1.",
    },
    # B3 Derivado
    {
        "sk_indicador": 29,
        "codigo": "RETORNO_DIARIO",
        "nome": "Retorno Diário",
        "fonte": "B3",
        "tipo": "derivado",
        "unidade": "%",
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

        # Define data inicial mínima garantindo 2020-12-31 para deltas de 2021
        min_date_str = min("2020-12-31", params.bacen_periodo[0], params.b3_periodo[0])
        max_date_str = max(params.bacen_periodo[1], params.b3_periodo[1])

        # Se houver anos CVM maiores, expande a data final para 31/12 do maior ano
        if params.cvm_anos:
            max_cvm_year = max(params.cvm_anos)
            cvm_end = f"{max_cvm_year}-12-31"
            if cvm_end > max_date_str:
                max_date_str = cvm_end

        # Carrega datas de pregão da Prata B3 para determinar dia_util_b3
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

            # Salva dimensões (substituição integral)
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