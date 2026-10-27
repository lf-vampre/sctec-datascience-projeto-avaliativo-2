"""Higienizador e limpador da camada Prata para demonstrativos contábeis da CVM (DRE, BPA, BPP)."""

from typing import List, Optional
import numpy as np
import pandas as pd

from src.etl.base import BaseCleaner, PipelineLogger
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


class CvmCleaner(BaseCleaner):
    """Limpador de demonstrativos contábeis CVM da camada Bronze para a camada Prata."""

    def __init__(
        self,
        logger: PipelineLogger,
        storage_writer: Optional[Persistence] = None,
    ) -> None:
        super().__init__(logger=logger, storage_writer=storage_writer)
        self.persistence = storage_writer or Persistence()

    def clean(self, params: PipelineParams) -> StepResult:
        """Lê Bronze da CVM (DRE, BPA, BPP), consolida escalas e versões e salva na Prata."""
        step_id = "clean_CvmCleaner"
        warnings: List[str] = []

        tables_map = {
            "cvm_dre": "DRE",
            "cvm_bpa": "BPA",
            "cvm_bpp": "BPP",
        }

        dfs: List[pd.DataFrame] = []

        # 1. Carregamento dos arquivos Bronze
        for table_name, dem_type in tables_map.items():
            df_table = self.persistence.load(
                layer="bronze",
                name=table_name,
                modo=params.modo,
            )
            if not df_table.empty:
                df_table["demonstrativo"] = dem_type
                dfs.append(df_table)
            release()

        if not dfs:
            msg = "Todos os DataFrames Bronze da CVM estão vazios."
            self.logger.emit("WARNING", "CvmCleaner", "LOAD", msg)
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                warnings=[msg],
                error=msg,
            )

        df = pd.concat(dfs, ignore_index=True)

        # 2. Padronização de Colunas e Tipos
        df.columns = [col.upper() for col in df.columns]

        required_cols = ["CD_CVM", "DT_FIM_EXERC", "CD_CONTA", "VL_CONTA", "VERSAO"]
        for col in required_cols:
            if col not in df.columns:
                err = f"Coluna obrigatória '{col}' ausente no Bronze CVM."
                return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=err)

        df["CD_CVM"] = pd.to_numeric(df["CD_CVM"], errors="coerce").astype("Int64")
        df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce").fillna(1).astype(int)
        df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")

        for dt_col in ["DT_REFER", "DT_FIM_EXERC", "DT_INI_EXERC"]:
            if dt_col in df.columns:
                df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")

        df = df.dropna(subset=["CD_CVM", "DT_FIM_EXERC", "CD_CONTA", "VL_CONTA"]).copy()
        df["CD_CVM"] = df["CD_CVM"].astype(int)

        # 3. Ajuste de Escala da Moeda (ESCALA_MOEDA)
        if "ESCALA_MOEDA" in df.columns:
            escala_str = df["ESCALA_MOEDA"].astype(str).str.strip().str.upper()
            unknown_mask = ~escala_str.isin(["MIL", "UNIDADE"]) & df["ESCALA_MOEDA"].notna()
            
            if unknown_mask.any():
                unk_count = unknown_mask.sum()
                msg_esc = f"Identificadas {unk_count} linhas com ESCALA_MOEDA desconhecida."
                self.logger.emit("WARNING", "CvmCleaner", "SCALE", msg_esc)
                warnings.append(msg_esc)

            mil_mask = escala_str == "MIL"
            df.loc[mil_mask, "VL_CONTA"] = df.loc[mil_mask, "VL_CONTA"] * 1000.0
        else:
            msg_no_scale = "Coluna ESCALA_MOEDA não encontrada. Assumindo valores brutos em R$."
            self.logger.emit("WARNING", "CvmCleaner", "SCALE", msg_no_scale)
            warnings.append(msg_no_scale)

        # Derivação do ano do exercício
        df["ano"] = df["DT_FIM_EXERC"].dt.year

        # 4. Verificação de Exercício Fiscal fora de Dezembro
        non_dec_mask = df["DT_FIM_EXERC"].dt.month != 12
        if non_dec_mask.any():
            non_dec_companies = df.loc[non_dec_mask, "CD_CVM"].unique().tolist()
            msg_non_dec = f"Empresas com exercício fiscal encerrando fora de dezembro (CD_CVM): {non_dec_companies}"
            self.logger.emit("WARNING", "CvmCleaner", "FISCAL_YEAR", msg_non_dec)
            warnings.append(msg_non_dec)

        # 5. Auditoria de Reapresentações (Diferença entre ÚLTIMO e PENÚLTIMO)
        if "ORDEM_EXERC" in df.columns:
            df_ult = df[df["ORDEM_EXERC"].astype(str).str.upper() == "ÚLTIMO"]
            df_pen = df[df["ORDEM_EXERC"].astype(str).str.upper() == "PENÚLTIMO"]

            keys = ["CD_CVM", "DEMONSTRATIVO", "CD_CONTA", "DT_FIM_EXERC"]
            merged = pd.merge(
                df_ult[keys + ["VL_CONTA"]],
                df_pen[keys + ["VL_CONTA"]],
                on=keys,
                suffixes=("_ULT", "_PEN"),
            )
            re_statement_diff = (merged["VL_CONTA_ULT"] != merged["VL_CONTA_PEN"]).sum()
            if re_statement_diff > 0:
                msg_re = f"Identificadas {re_statement_diff} contas com divergência de valor entre ÚLTIMO e PENÚLTIMO (reapresentações)."
                self.logger.emit("INFO", "CvmCleaner", "RESTATEMENT", msg_re)

        # 6. Desduplicação por Versão e Exercício
        # Prioridade: Maior VERSAO -> Se empate, ORDEM_EXERC == 'ÚLTIMO'
        df["_is_ultimo"] = (df["ORDEM_EXERC"].astype(str).str.upper() == "ÚLTIMO").astype(int) if "ORDEM_EXERC" in df.columns else 0

        group_keys = ["CD_CVM", "DEMONSTRATIVO", "CD_CONTA", "DT_FIM_EXERC"]
        df = df.sort_values(
            by=group_keys + ["VERSAO", "_is_ultimo"],
            ascending=[True, True, True, True, True, True],
        )

        duplicates_count = df.duplicated(subset=group_keys, keep="last").sum()
        if duplicates_count > 0:
            df = df.drop_duplicates(subset=group_keys, keep="last").copy()
            msg_dedup = f"Removidas {duplicates_count} duplicatas/versões anteriores mantendo a VERSAO mais recente."
            self.logger.emit("INFO", "CvmCleaner", "DEDUP", msg_dedup)

        df.drop(columns=["_is_ultimo"], inplace=True, errors="ignore")

        # 7. Normalização final de nomes de colunas para minúsculo
        df.columns = [col.lower() for col in df.columns]

        cols_to_save = [
            "cd_cvm",
            "demonstrativo",
            "cd_conta",
            "ds_conta",
            "st_conta_fixa",
            "dt_fim_exerc",
            "dt_refer",
            "dt_ini_exerc",
            "vl_conta",
            "versao",
            "ano",
        ]
        available_cols = [c for c in cols_to_save if c in df.columns]

        if "_ingest_ts" in df.columns:
            available_cols.append("_ingest_ts")
        if "_run_id" in df.columns:
            available_cols.append("_run_id")

        # 8. Persistência na Prata
        save_res = self.persistence.save(
            layer="silver",
            name="cvm_demonstrativos",
            df=df[available_cols],
            partition_cols=["cd_cvm", "ano"],
            modo=params.modo,
        )

        self.logger.emit(
            "INFO",
            "CvmCleaner",
            "CLEAN_SUCCESS",
            f"Prata CVM gravada em {save_res['parquet_path']} ({save_res['rows']} linhas)",
        )

        return StepResult(
            step_id=step_id,
            ok=True,
            rows=len(df),
            paths=[save_res["parquet_path"]],
            warnings=warnings,
        )