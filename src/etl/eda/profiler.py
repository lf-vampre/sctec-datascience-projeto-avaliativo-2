"""Profiler de Análise Exploratória de Dados (EDA) somente leitura sobre a camada Prata."""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config import settings
from src.config.universe import COMPANIES
from src.etl.warehouse.persistence import Persistence


@dataclass
class Achado:
    """Representa uma constatação auditável de qualidade de dados."""

    id: str
    severidade: str  # "info", "atencao", "critico"
    titulo: str
    detalhe: str
    metrica: str
    acao_sugerida: str


@dataclass
class RelatorioEDA:
    """Contêiner do relatório de Análise Exploratória de Dados."""

    resumo: Dict[str, Any] = field(default_factory=dict)
    tabelas: Dict[str, pd.DataFrame] = field(default_factory=dict)
    achados: List[Achado] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)


class DataProfiler:
    """Realiza profilagem e diagnósticos de qualidade somente leitura sobre a camada Prata."""

    FONTE_TABELA = {
        "bacen": "bacen_sgs",
        "b3": "b3_cotacoes",
        "cvm": "cvm_demonstrativos",
        "cadastro": "cvm_cadastro",
    }

    def __init__(self, persistence: Optional[Persistence] = None) -> None:
        self.persistence = persistence or Persistence()

    def perfil(self, fonte: str, modo: str = "producao", df_custom: Optional[pd.DataFrame] = None) -> RelatorioEDA:
        """Gera o relatório de EDA para a fonte especificada sem alterar os dados de entrada."""
        fonte_clean = fonte.strip().lower()
        if fonte_clean not in self.FONTE_TABELA:
            raise ValueError(f"Fonte inválida '{fonte}'. Opções: {list(self.FONTE_TABELA.keys())}")

        tabela_nome = self.FONTE_TABELA[fonte_clean]
        
        if df_custom is not None:
            df = df_custom.copy()
        else:
            df = self.persistence.load(layer="silver", name=tabela_nome, modo=modo)

        relatorio = RelatorioEDA()
        
        if df.empty:
            relatorio.resumo = {
                "fonte": fonte_clean,
                "tabela": tabela_nome,
                "linhas": 0,
                "colunas": 0,
                "periodo": "N/A",
                "data_geracao": datetime.now().isoformat(),
            }
            relatorio.avisos.append(f"Tabela silver.{tabela_nome} está vazia no modo {modo}.")
            relatorio.achados.append(
                Achado(
                    id="EMPTY_TABLE",
                    severidade="critico",
                    titulo="Tabela Silver Vazia",
                    detalhe=f"A tabela silver.{tabela_nome} não contém registros.",
                    metrica="linhas = 0",
                    acao_sugerida="Executar o pipeline de ingestão e limpeza Prata.",
                )
            )
            return relatorio

        # Diagnósticos comuns
        self._verificacoes_comuns(df, tabela_nome, relatorio)

        # Diagnósticos específicos por fonte
        if fonte_clean == "bacen":
            self._perfil_bacen(df, relatorio)
        elif fonte_clean == "b3":
            self._perfil_b3(df, relatorio)
        elif fonte_clean == "cvm":
            self._perfil_cvm(df, relatorio)
        elif fonte_clean == "cadastro":
            self._perfil_cadastro(df, relatorio)

        return relatorio

    def _verificacoes_comuns(self, df: pd.DataFrame, tabela_nome: str, relatorio: RelatorioEDA) -> None:
        """Executa verificações genéricas de nulos, duplicatas e tipos."""
        num_linhas = len(df)
        num_colunas = len(df.columns)

        # Resumo inicial
        periodo_str = "N/A"
        col_data = next((c for c in ["data", "dt_refer", "DT_FIM_EXERC"] if c in df.columns), None)
        if col_data and not df[col_data].dropna().empty:
            datas = pd.to_datetime(df[col_data].dropna())
            periodo_str = f"{datas.min().strftime('%Y-%m-%d')} a {datas.max().strftime('%Y-%m-%d')}"

        relatorio.resumo = {
            "tabela": tabela_nome,
            "linhas": num_linhas,
            "colunas": num_colunas,
            "periodo": periodo_str,
            "data_geracao": datetime.now().isoformat(),
        }

        # Nulos por coluna
        nulos_col = df.isnull().sum()
        pct_nulos = (nulos_col / num_linhas) * 100
        df_nulos = pd.DataFrame({"nulos_qtd": nulos_col, "nulos_pct": pct_nulos})
        relatorio.tabelas["nulos_por_coluna"] = df_nulos

        # Estatísticas descritivas
        cols_num = df.select_dtypes(include=[np.number]).columns
        if len(cols_num) > 0:
            relatorio.tabelas["estatisticas_descritivas"] = df[cols_num].describe().T

    def _perfil_bacen(self, df: pd.DataFrame, relatorio: RelatorioEDA) -> None:
        """Profilagem específica das séries temporais do BACEN."""
        chaves = ["codigo_sgs", "data"]
        cols_chave = [c for c in chaves if c in df.columns]
        if len(cols_chave) == 2:
            dup_count = df.duplicated(subset=cols_chave).sum()
            if dup_count > 0:
                relatorio.achados.append(
                    Achado(
                        id="BACEN_DUPLICATES",
                        severidade="critico",
                        titulo="Duplicatas na Chave Natural BACEN",
                        detalhe=f"Foram encontradas {dup_count} duplicatas para a combinação (codigo_sgs, data).",
                        metrica=f"duplicatas = {dup_count}",
                        acao_sugerida="Verificar deduplicação no BacenCleaner.",
                    )
                )

        if "codigo_sgs" in df.columns and "valor" in df.columns and "data" in df.columns:
            resumo_series = []
            df_work = df.copy()
            df_work["data"] = pd.to_datetime(df_work["data"])

            for cod, grp in df_work.groupby("codigo_sgs"):
                grp = grp.sort_values("data")
                qtd_obs = len(grp)
                dt_min = grp["data"].min()
                dt_max = grp["data"].max()

                s_vals = grp["valor"].dropna()
                mediana = s_vals.median() if not s_vals.empty else np.nan
                q1 = s_vals.quantile(0.25) if not s_vals.empty else np.nan
                q3 = s_vals.quantile(0.75) if not s_vals.empty else np.nan
                iqr = q3 - q1 if not s_vals.empty else np.nan
                mad = (s_vals - mediana).abs().median() if not s_vals.empty else np.nan

                # Outliers por IQR e MAD
                outliers_iqr = 0
                outliers_mad = 0
                if iqr > 0 and not s_vals.empty:
                    lim_inf = q1 - settings.EDA_OUTLIER_IQR_FACTOR * iqr
                    lim_sup = q3 + settings.EDA_OUTLIER_IQR_FACTOR * iqr
                    outliers_iqr = ((s_vals < lim_inf) | (s_vals > lim_sup)).sum()

                if mad > 0 and not s_vals.empty:
                    # Robust Z-score = 0.6745 * (x - median) / MAD
                    z_robust = 0.6745 * (s_vals - mediana).abs() / mad
                    outliers_mad = (z_robust > settings.EDA_OUTLIER_MAD_THRESHOLD).sum()

                # Checagem de Séries em Degrau (Selic)
                is_degrau = cod in [432, 1178]
                if is_degrau:
                    fora_faixa = ((s_vals < 0) | (s_vals > 100)).sum()
                    if fora_faixa > 0:
                        relatorio.achados.append(
                            Achado(
                                id=f"BACEN_OUT_OF_RANGE_{cod}",
                                severidade="critico",
                                titulo=f"Selic Fora da Faixa Plausível (SGS {cod})",
                                detalhe=f"Foram encontrados {fora_faixa} valores fora do intervalo [0%, 100%].",
                                metrica=f"fora_faixa = {fora_faixa}",
                                acao_sugerida="Investigar erros de escala ou digitação na série BACEN.",
                            )
                        )
                elif outliers_iqr > 0:
                    relatorio.achados.append(
                        Achado(
                            id=f"BACEN_OUTLIER_IQR_{cod}",
                            severidade="atencao",
                            titulo=f"Valores Atípicos Detectados via IQR (SGS {cod})",
                            detalhe=f"A série SGS {cod} possui {outliers_iqr} observações fora dos limites de IQR.",
                            metrica=f"outliers_iqr = {outliers_iqr}",
                            acao_sugerida="Avaliar choque macroeconômico vs erro estatístico.",
                        )
                    )

                resumo_series.append({
                    "codigo_sgs": cod,
                    "obs_qtd": qtd_obs,
                    "dt_min": dt_min.strftime("%Y-%m-%d"),
                    "dt_max": dt_max.strftime("%Y-%m-%d"),
                    "mediana": mediana,
                    "iqr": iqr,
                    "mad": mad,
                    "outliers_iqr": outliers_iqr,
                    "outliers_mad": outliers_mad,
                })

            relatorio.tabelas["resumo_series_bacen"] = pd.DataFrame(resumo_series)

    def _perfil_b3(self, df: pd.DataFrame, relatorio: RelatorioEDA) -> None:
        """Profilagem das cotações diárias da B3."""
        cols_chave = [c for c in ["ticker", "data"] if c in df.columns]
        if len(cols_chave) == 2:
            dup_count = df.duplicated(subset=cols_chave).sum()
            if dup_count > 0:
                relatorio.achados.append(
                    Achado(
                        id="B3_DUPLICATES",
                        severidade="critico",
                        titulo="Duplicatas na Chave Natural B3",
                        detalhe=f"Foram encontradas {dup_count} duplicatas para (ticker, data).",
                        metrica=f"duplicatas = {dup_count}",
                        acao_sugerida="Verificar deduplicação em B3Cleaner.",
                    )
                )

        if "ticker" in df.columns and "data" in df.columns and "close" in df.columns:
            df_work = df.copy()
            df_work["data"] = pd.to_datetime(df_work["data"])
            df_work = df_work.sort_values(["ticker", "data"])

            max_pregoes = df_work.groupby("ticker")["data"].nunique().max()
            metrics_b3 = []

            for ticker, grp in df_work.groupby("ticker"):
                pregoes = grp["data"].nunique()
                cobertura_pct = (pregoes / max_pregoes * 100) if max_pregoes > 0 else 0.0
                
                # Diagnóstico de retorno diário
                retornos = grp["close"].pct_change().dropna()
                n = len(retornos)
                skew = retornos.skew() if n > 3 else np.nan
                kurt = retornos.kurtosis() if n > 3 else np.nan

                # Estatística de Jarque-Bera: JB = (n/6) * (S^2 + ((K-3)^2)/4)
                # Note: pandas .kurtosis() retorna excess kurtosis (K-3)
                jb_stat = np.nan
                jb_pvalue = np.nan
                if n >= settings.EDA_MIN_OBSERVATIONS and not np.isnan(skew) and not np.isnan(kurt):
                    jb_stat = (n / 6.0) * (skew**2 + (kurt**2) / 4.0)
                    jb_pvalue = math.exp(-jb_stat / 2.0)

                # Retornos extremos
                extremos_qtd = (retornos.abs() > settings.EDA_B3_EXTREME_RETURN_THRESHOLD).sum()
                if extremos_qtd > 0:
                    relatorio.achados.append(
                        Achado(
                            id=f"B3_EXTREME_RETURNS_{ticker}",
                            severidade="atencao",
                            titulo=f"Retornos Diários Extremos em {ticker}",
                            detalhe=f"O ativo {ticker} teve {extremos_qtd} pregões com variação diária absoluta > {settings.EDA_B3_EXTREME_RETURN_THRESHOLD:.0%}.",
                            metrica=f"extremos_qtd = {extremos_qtd}",
                            acao_sugerida="Verificar se houve agrupamento/desdobramento de ações ou evento corporativo.",
                        )
                    )

                # Jarque-Bera rejeição de normalidade (p-value < 0.05)
                if not np.isnan(jb_pvalue) and jb_pvalue < 0.05:
                    relatorio.achados.append(
                        Achado(
                            id=f"B3_NON_NORMALITY_{ticker}",
                            severidade="info",
                            titulo=f"Rejeição de Normalidade nos Retornos ({ticker})",
                            detalhe=f"O teste de Jarque-Bera (p-valor={jb_pvalue:.4e}) indica caudas pesadas nos retornos.",
                            metrica=f"JB = {jb_stat:.2f}, p-valor = {jb_pvalue:.4e}",
                            acao_sugerida="Justifica cautela no Sharpe Ratio assumindo distribuição com caudas largas (DM-02).",
                        )
                    )

                # Volume zero ou flag de qualidade
                vol_zero = (grp["volume"] == 0).sum() if "volume" in grp.columns else 0
                flag_qualidade = (grp["flag_qualidade"] != "OK").sum() if "flag_qualidade" in grp.columns else 0

                metrics_b3.append({
                    "ticker": ticker,
                    "pregoes": pregoes,
                    "cobertura_pct": cobertura_pct,
                    "retorno_medio_diario": retornos.mean() if n > 0 else np.nan,
                    "volatilidade_diaria": retornos.std() if n > 0 else np.nan,
                    "assimetria": skew,
                    "curtose": kurt,
                    "jb_stat": jb_stat,
                    "jb_pvalue": jb_pvalue,
                    "extremos_qtd": extremos_qtd,
                    "vol_zero_qtd": vol_zero,
                    "flag_qualidade_qtd": flag_qualidade,
                })

            relatorio.tabelas["metricas_b3"] = pd.DataFrame(metrics_b3)

    def _perfil_cvm(self, df: pd.DataFrame, relatorio: RelatorioEDA) -> None:
        """Profilagem dos demonstrativos contábeis da CVM."""
        cols_chave = [c for c in ["cd_cvm", "DT_FIM_EXERC", "cd_conta"] if c in df.columns]
        if len(cols_chave) == 3:
            dup_count = df.duplicated(subset=cols_chave).sum()
            if dup_count > 0:
                relatorio.achados.append(
                    Achado(
                        id="CVM_DUPLICATES",
                        severidade="critico",
                        titulo="Duplicatas na Chave Natural CVM",
                        detalhe=f"Foram encontradas {dup_count} duplicatas para (cd_cvm, DT_FIM_EXERC, cd_conta).",
                        metrica=f"duplicatas = {dup_count}",
                        acao_sugerida="Verificar consolidação e versão DFP no CvmCleaner.",
                    )
                )

        if "cd_cvm" in df.columns and "cd_conta" in df.columns and "vl_conta" in df.columns:
            # Análise por tipo de plano (financeiras vs industriais)
            bancos_cvm = {info.cd_cvm for info in COMPANIES.values() if info.tipo_plano == "financeira"}
            
            # Checar razões contábeis atípicas
            # Agrupar contas por cd_cvm e exercício
            pivoted = df.pivot_table(
                index=["cd_cvm", "DT_FIM_EXERC"],
                columns="cd_conta",
                values="vl_conta",
                aggfunc="last"
            ).reset_index()

            for _, row in pivoted.iterrows():
                cd_cvm = row["cd_cvm"]
                exerc = row["DT_FIM_EXERC"]
                is_banco = cd_cvm in bancos_cvm

                rl = row.get("3.01", np.nan)
                ebit = row.get("3.05", np.nan)
                ll = row.get("3.11", np.nan)
                pl = row.get("2.03", np.nan)

                # Margem EBIT / Margem Líquida em não financeiras
                if not is_banco:
                    if pd.notna(rl) and rl > 0:
                        if pd.notna(ebit) and (ebit / rl > 1.0 or ebit / rl < -2.0):
                            relatorio.achados.append(
                                Achado(
                                    id=f"CVM_EBIT_MARGIN_{cd_cvm}_{exerc}",
                                    severidade="atencao",
                                    titulo="Margem EBIT Atípica",
                                    detalhe=f"Empresa CVM {cd_cvm} no exercício {exerc} possui Margem EBIT atípica ({(ebit/rl):.1%}).",
                                    metrica=f"ebit/rl = {ebit/rl:.2f}",
                                    acao_sugerida="Avaliar itens não recorrentes ou reclassificação no DRE.",
                                )
                            )

                # Patrimônio Líquido negativo
                if pd.notna(pl) and pl <= 0:
                    relatorio.achados.append(
                        Achado(
                            id=f"CVM_NEGATIVE_EQUITY_{cd_cvm}_{exerc}",
                            severidade="atencao",
                            titulo="Patrimônio Líquido Nulo ou Negativo",
                            detalhe=f"Empresa CVM {cd_cvm} no exercício {exerc} apresenta PL ≤ 0 (R$ {pl:,.2f}).",
                            metrica=f"pl = {pl}",
                            acao_sugerida="Passivo a descoberto detectado; ROE e alavancagem exigem ressalva.",
                        )
                    )

                # Ausência estrutural em bancos (esperada)
                if is_banco:
                    relatorio.achados.append(
                        Achado(
                            id=f"CVM_BANK_STRUCTURAL_NULLS_{cd_cvm}_{exerc}",
                            severidade="info",
                            titulo="Nulos Estruturais em Instituição Financeira (ADR-09)",
                            detalhe=f"Empresa CVM {cd_cvm} (financeira) não possui Margem EBIT / Liquidez Corrente aplicáveis.",
                            metrica="tipo_plano = financeira",
                            acao_sugerida="Ausência correta segundo ADR-09; sem ação corretiva.",
                        )
                    )

            relatorio.achados.append(
                Achado(
                    id="CVM_REPRESENTATIONS_STATUS",
                    severidade="info",
                    titulo="Status de Reapresentação DFP",
                    detalhe="A Prata mantém a versão mais recente da DFP. Reapresentações intermediárias desconsideradas.",
                    metrica="versao = ultima",
                    acao_sugerida="Nenhuma.",
                )
            )

    def _perfil_cadastro(self, df: pd.DataFrame, relatorio: RelatorioEDA) -> None:
        """Profilagem das informações cadastrais das empresas."""
        cols_unicas = [c for c in ["cd_cvm", "cnpj"] if c in df.columns]
        for col in cols_unicas:
            dup_cnt = df.duplicated(subset=[col]).sum()
            if dup_cnt > 0:
                relatorio.achados.append(
                    Achado(
                        id=f"CADASTRO_DUPLICATE_{col.upper()}",
                        severidade="critico",
                        titulo=f"Duplicatas na Coluna Cadastral {col}",
                        detalhe=f"A coluna {col} possui {dup_cnt} valores duplicados.",
                        metrica=f"duplicatas = {dup_cnt}",
                        acao_sugerida="Validar deduplicação em CadastroCleaner.",
                    )
                )

        if "sit_cad" in df.columns:
            inativas = (df["sit_cad"] != "ATIVO").sum()
            if inativas > 0:
                relatorio.achados.append(
                    Achado(
                        id="CADASTRO_INACTIVE_COMPANIES",
                        severidade="atencao",
                        titulo="Empresas Não Ativas Encontradas",
                        detalhe=f"Foram encontradas {inativas} empresas com situação cadastral diferente de ATIVO.",
                        metrica=f"inativas = {inativas}",
                        acao_sugerida="Verificar se há empresas canceladas ou suspensas no universo.",
                    )
                )