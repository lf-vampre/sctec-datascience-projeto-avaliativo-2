"""Higienizador e limpador da camada Prata para dados cadastrais de companhias da CVM."""

import re
from typing import List, Optional
import pandas as pd

from src.config.universe import COMPANIES
from src.etl.base import BaseCleaner, PipelineLogger
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


class CadastroCleaner(BaseCleaner):
    """Limpador de dados cadastrais CVM da camada Bronze para a camada Prata."""

    def __init__(
        self,
        logger: PipelineLogger,
        storage_writer: Optional[Persistence] = None,
    ) -> None:
        super().__init__(logger=logger, storage_writer=storage_writer)
        self.persistence = storage_writer or Persistence()

    def clean(self, params: PipelineParams) -> StepResult:
        """Lê Bronze do cadastro CVM, padroniza, valida regras de integridade e salva na Prata."""
        step_id = "clean_CadastroCleaner"
        warnings: List[str] = []

        # 1. Carregamento do Bronze
        df_bronze = self.persistence.load(
            layer="bronze",
            name="cvm_cadastro",
            modo=params.modo,
        )

        if df_bronze.empty:
            msg = "DataFrame Bronze do Cadastro CVM está vazio."
            self.logger.emit("WARNING", "CadastroCleaner", "LOAD", msg)
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                warnings=[msg],
                error=msg,
            )

        df = df_bronze.copy()

        # 2. Padronização de nomes de colunas em snake_case minúsculo
        col_rename_map = {
            "CD_CVM": "cd_cvm",
            "CNPJ_CIA": "cnpj",
            "DENOM_SOC": "denom_social",
            "DENOM_COM": "denom_comercial",
            "SIT": "situacao",
            "SETOR_ATIV": "setor_ativ",
            "DT_REG": "dt_reg",
            "DT_CANCEL": "dt_cancel",
            "TP_MERC": "tp_merc",
        }
        
        df.columns = [col_rename_map.get(col, col.lower().strip()) for col in df.columns]

        # 3. Tipos e Limpeza de Textos
        if "cd_cvm" in df.columns:
            df["cd_cvm"] = pd.to_numeric(df["cd_cvm"], errors="coerce").astype("Int64")
        else:
            err = "Coluna 'cd_cvm' ausente no Bronze do Cadastro CVM."
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=err)

        for text_col in ["denom_social", "denom_comercial", "situacao", "setor_ativ", "tp_merc"]:
            if text_col in df.columns:
                df[text_col] = (
                    df[text_col]
                    .astype(str)
                    .str.strip()
                    .str.replace(r"\s+", " ", regex=True)
                )

        for dt_col in ["dt_reg", "dt_cancel"]:
            if dt_col in df.columns:
                df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")

        df = df.dropna(subset=["cd_cvm"]).copy()
        df["cd_cvm"] = df["cd_cvm"].astype(int)

        # 4. Normalização e Validação do CNPJ
        if "cnpj" in df.columns:
            df["cnpj"] = df["cnpj"].astype(str).str.strip()
            df["cnpj_limpo"] = df["cnpj"].apply(lambda x: re.sub(r"\D", "", x))

            invalid_cnpj_mask = df["cnpj_limpo"].str.len() != 14
            if invalid_cnpj_mask.any():
                invalid_count = invalid_cnpj_mask.sum()
                msg_cnpj = f"Identificados {invalid_count} CNPJs com tamanho diferente de 14 dígitos."
                self.logger.emit("WARNING", "CadastroCleaner", "CNPJ_CHECK", msg_cnpj)
                warnings.append(msg_cnpj)
        else:
            df["cnpj"] = None
            df["cnpj_limpo"] = None

        # 5. Unicidade por cd_cvm
        duplicates_count = df.duplicated(subset=["cd_cvm"], keep=False).sum()
        if duplicates_count > 0:
            initial_len = len(df)
            # Prioriza registros ativos (sem dt_cancel e com situação CONCEDITO/ATIVO)
            if "situacao" in df.columns:
                df["_is_ativo"] = df["situacao"].str.upper().str.contains("CANCEL", regex=False) == False
                df = df.sort_values(by=["cd_cvm", "_is_ativo"], ascending=[True, True])
                df.drop(columns=["_is_ativo"], inplace=True)
            
            df = df.drop_duplicates(subset=["cd_cvm"], keep="last").copy()
            dedup_removed = initial_len - len(df)
            msg_dedup = f"Removidas {dedup_removed} duplicatas de cd_cvm no Cadastro CVM."
            self.logger.emit("WARNING", "CadastroCleaner", "DEDUP", msg_dedup)
            warnings.append(msg_dedup)

        # 6. Verificações de Regra de Negócio e Integridade Universo
        # 6.1 Mapeamento Ticker <-> CVM
        universe_cvm_map = {info.cd_cvm: ticker for ticker, info in COMPANIES.items()}
        cvm_in_cad = set(df["cd_cvm"].unique())

        # Check: Tickers do universo sem cd_cvm no cadastro
        requested_tickers = params.tickers or list(COMPANIES.keys())
        for ticker in requested_tickers:
            if ticker in COMPANIES:
                company_cvm = COMPANIES[ticker].cd_cvm
                if company_cvm not in cvm_in_cad:
                    msg_missing = f"Ticker {ticker} (CD_CVM {company_cvm}) não foi encontrado no Cadastro CVM."
                    self.logger.emit("WARNING", "CadastroCleaner", "UNIVERSE_CHECK", msg_missing)
                    warnings.append(msg_missing)

        # Check: Situação inativa ou cancelada nas empresas do cadastro
        if "situacao" in df.columns:
            for _, row in df.iterrows():
                cvm_code = row["cd_cvm"]
                sit = str(row["situacao"]).upper()
                if cvm_code in universe_cvm_map:
                    if any(term in sit for term in ["CANCEL", "INATIV"]):
                        tkr = universe_cvm_map[cvm_code]
                        msg_sit = f"Companhia {tkr} (CD_CVM {cvm_code}) está com situação '{row['situacao']}' no Cadastro."
                        self.logger.emit("WARNING", "CadastroCleaner", "SITUATION_CHECK", msg_sit)
                        warnings.append(msg_sit)

        # Check: Mesmo cd_cvm atribuído a dois tickers no universo
        cvm_to_tickers = {}
        for ticker, info in COMPANIES.items():
            cvm_to_tickers.setdefault(info.cd_cvm, []).append(ticker)
        
        for cvm_code, tkr_list in cvm_to_tickers.items():
            if len(tkr_list) > 1:
                msg_multi = f"Mesmo CD_CVM {cvm_code} atribuído a múltiplos tickers: {tkr_list}"
                self.logger.emit("WARNING", "CadastroCleaner", "UNIVERSE_CHECK", msg_multi)
                warnings.append(msg_multi)

        # 7. Persistência na Prata
        cols_to_save = [
            "cd_cvm",
            "cnpj",
            "cnpj_limpo",
            "denom_social",
            "denom_comercial",
            "situacao",
            "setor_ativ",
            "dt_reg",
            "dt_cancel",
            "tp_merc",
        ]
        available_cols = [c for c in cols_to_save if c in df.columns]

        if "_ingest_ts" in df.columns:
            available_cols.append("_ingest_ts")
        if "_run_id" in df.columns:
            available_cols.append("_run_id")

        save_res = self.persistence.save(
            layer="silver",
            name="cvm_cadastro",
            df=df[available_cols],
            partition_cols=["cd_cvm"],
            modo=params.modo,
        )

        release()

        self.logger.emit(
            "INFO",
            "CadastroCleaner",
            "CLEAN_SUCCESS",
            f"Prata Cadastro CVM gravada em {save_res['parquet_path']} ({save_res['rows']} linhas)",
        )

        return StepResult(
            step_id=step_id,
            ok=True,
            rows=len(df),
            paths=[save_res["parquet_path"]],
            warnings=warnings,
        )