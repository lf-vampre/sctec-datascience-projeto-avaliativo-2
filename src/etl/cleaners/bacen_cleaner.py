"""Higienizador e limpador da camada Prata para dados do BACEN SGS."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.config import settings
from src.etl.base import BaseCleaner, PipelineLogger
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


class BacenCleaner(BaseCleaner):
    """Limpador de dados da camada Bronze do BACEN para a camada Prata."""

    def __init__(
        self,
        logger: PipelineLogger,
        storage_writer: Optional[Persistence] = None,
    ) -> None:
        super().__init__(logger=logger, storage_writer=storage_writer)
        self.persistence = storage_writer or Persistence()

    def _build_sgs_map(self) -> Dict[int, str]:
        """Constrói mapa reverso sgs_codigo -> codigo de indicador."""
        sgs_map = {}
        for code, info in settings.BACEN_SERIES.items():
            sgs_map[info["sgs_codigo"]] = code
        return sgs_map

    def clean(self, params: PipelineParams) -> StepResult:
        """Lê Bronze do BACEN, higieniza, aplica validações de consistência e salva na Prata."""
        step_id = "clean_BacenCleaner"
        warnings: List[str] = []

        # 1. Carregamento do Bronze
        df_bronze = self.persistence.load(
            layer="bronze",
            name="bacen_sgs",
            modo=params.modo,
        )

        if df_bronze.empty:
            msg = "DataFrame Bronze do BACEN está vazio."
            self.logger.emit("WARNING", "BacenCleaner", "LOAD", msg)
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                warnings=[msg],
                error=msg,
            )

        df = df_bronze.copy()
        rows_initial = len(df)

        # 2. Conversão e Padronização de Tipos
        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
        else:
            err = "Coluna 'data' ausente no Bronze BACEN."
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=err)

        if "valor" in df.columns:
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        else:
            err = "Coluna 'valor' ausente no Bronze BACEN."
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=err)

        if "serie_codigo" in df.columns:
            df["serie_codigo"] = pd.to_numeric(df["serie_codigo"], errors="coerce").astype("Int64")
        else:
            err = "Coluna 'serie_codigo' ausente no Bronze BACEN."
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=err)

        # Mapeamento do código do indicador
        sgs_map = self._build_sgs_map()
        df["codigo"] = df["serie_codigo"].map(sgs_map)

        # 3. Tratamento de Nulos e Duplicatas
        null_count = df["data"].isna().sum() + df["valor"].isna().sum()
        if null_count > 0:
            df = df.dropna(subset=["data", "valor", "serie_codigo"])
            msg_nulls = f"Removidos {null_count} registros com valores/datas nulos ou inválidos."
            self.logger.emit("WARNING", "BacenCleaner", "SANITY", msg_nulls)
            warnings.append(msg_nulls)

        df["serie_codigo"] = df["serie_codigo"].astype(int)

        duplicates_count = df.duplicated(subset=["serie_codigo", "data"]).sum()
        if duplicates_count > 0:
            df = df.drop_duplicates(subset=["serie_codigo", "data"], keep="last")
            msg_dup = f"Removidas {duplicates_count} duplicatas por (serie_codigo, data)."
            self.logger.emit("WARNING", "BacenCleaner", "SANITY", msg_dup)
            warnings.append(msg_dup)

        # Ordenação
        if not df.empty:
            df = df.sort_values(by=["serie_codigo", "data"]).reset_index(drop=True)

        # 4. Regras de Consistência e Alertas
        sgs_by_code = {v["sgs_codigo"]: k for k, v in settings.BACEN_SERIES.items()}

        for sgs_code, df_group in df.groupby("serie_codigo"):
            indicator_code = sgs_by_code.get(sgs_code, str(sgs_code))
            info = settings.BACEN_SERIES.get(indicator_code, {})
            gran = info.get("granularidade", "")

            # Granularidade mensal: verifica dia 1 e duplicatas no mês
            if gran == "mensal":
                not_first_day = (df_group["data"].dt.day != 1).sum()
                if not_first_day > 0:
                    warn_gran = f"Série {indicator_code} ({sgs_code}): {not_first_day} registros fora do dia 1 do mês."
                    self.logger.emit("WARNING", "BacenCleaner", "CONSISTENCY", warn_gran)
                    warnings.append(warn_gran)

                month_dups = df_group["data"].dt.to_period("M").duplicated().sum()
                if month_dups > 0:
                    warn_mdup = f"Série {indicator_code} ({sgs_code}): {month_dups} observações duplicadas no mesmo mês."
                    self.logger.emit("WARNING", "BacenCleaner", "CONSISTENCY", warn_mdup)
                    warnings.append(warn_mdup)

            # Faixas plausíveis
            if indicator_code in {"SELIC_META", "SELIC_EFETIVA"} and (df_group["valor"] < 0).any():
                warn_range = f"Série {indicator_code}: identificados valores negativos de taxa Selic."
                self.logger.emit("WARNING", "BacenCleaner", "RANGE", warn_range)
                warnings.append(warn_range)

            if indicator_code in {"PTAX_VENDA", "IBC_BR_SA"} and (df_group["valor"] <= 0).any():
                warn_range = f"Série {indicator_code}: identificados valores não positivos (<= 0)."
                self.logger.emit("WARNING", "BacenCleaner", "RANGE", warn_range)
                warnings.append(warn_range)

            # Cobertura temporal
            if not df_group.empty:
                min_dt = df_group["data"].min().strftime("%Y-%m-%d")
                max_dt = df_group["data"].max().strftime("%Y-%m-%d")
                self.logger.emit(
                    "INFO",
                    "BacenCleaner",
                    "COVERAGE",
                    f"Série {indicator_code}: amplitude {min_dt} até {max_dt} ({len(df_group)} registros)",
                )

        # Coerência IPCA (12M acumulado vs composto mensal 12M)
        sgs_ipca_m = settings.BACEN_SERIES["IPCA_MENSAL"]["sgs_codigo"]
        sgs_ipca_12m = settings.BACEN_SERIES["IPCA_12M"]["sgs_codigo"]

        df_ipca_m = df[df["serie_codigo"] == sgs_ipca_m].sort_values("data")
        df_ipca_12m = df[df["serie_codigo"] == sgs_ipca_12m].sort_values("data")

        if not df_ipca_m.empty and not df_ipca_12m.empty:
            ipca_m_map = dict(zip(df_ipca_m["data"].dt.to_period("M"), df_ipca_m["valor"]))
            tolerance = 0.5  # Tolerância de 0.5 pp devido a arredondamento oficial por número índice

            for _, row_12m in df_ipca_12m.iterrows():
                dt_end = row_12m["data"].to_period("M")
                periods_12 = [dt_end - i for i in range(12)]
                vals_12 = [ipca_m_map.get(p) for p in periods_12]

                if all(v is not None for v in vals_12):
                    compounded = (np.prod([1 + v / 100.0 for v in vals_12]) - 1) * 100.0
                    diff = abs(row_12m["valor"] - compounded)
                    if diff > tolerance:
                        warn_ipca = (
                            f"Incoerência IPCA em {dt_end}: IPCA 12M do BACEN ({row_12m['valor']:.2f}%) "
                            f"diverge do acumulado composto dos 12m ({compounded:.2f}%) por {diff:.2f} pp."
                        )
                        self.logger.emit("WARNING", "BacenCleaner", "IPCA_COHERENCE", warn_ipca)
                        warnings.append(warn_ipca)
                        break

        # 5. Persistência na Prata
        cols_to_save = ["data", "valor", "serie_codigo", "codigo"]
        if "_ingest_ts" in df.columns:
            cols_to_save.append("_ingest_ts")
        if "_run_id" in df.columns:
            cols_to_save.append("_run_id")

        save_res = self.persistence.save(
            layer="silver",
            name="bacen_sgs",
            df=df[cols_to_save],
            partition_cols=["serie_codigo"],
            modo=params.modo,
        )

        self.logger.emit(
            "INFO",
            "BacenCleaner",
            "CLEAN_SUCCESS",
            f"Prata BACEN gravada em {save_res['parquet_path']} ({save_res['rows']} linhas)",
        )

        release()

        return StepResult(
            step_id=step_id,
            ok=True,
            rows=len(df),
            paths=[save_res["parquet_path"]],
            warnings=warnings,
        )