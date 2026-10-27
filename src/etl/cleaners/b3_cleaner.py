"""Higienizador e limpador da camada Prata para cotações da B3."""

from typing import List, Optional
import numpy as np
import pandas as pd

from src.config import settings
from src.etl.base import BaseCleaner, PipelineLogger
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult


class B3Cleaner(BaseCleaner):
    """Limpador de dados de cotações B3 da camada Bronze para a camada Prata."""

    def __init__(
        self,
        logger: PipelineLogger,
        storage_writer: Optional[Persistence] = None,
    ) -> None:
        super().__init__(logger=logger, storage_writer=storage_writer)
        self.persistence = storage_writer or Persistence()

    def clean(self, params: PipelineParams) -> StepResult:
        """Lê Bronze da B3, higieniza, aplica validações de consistência e salva na Prata."""
        step_id = "clean_B3Cleaner"
        warnings: List[str] = []

        # 1. Carregamento do Bronze
        df_bronze = self.persistence.load(
            layer="bronze",
            name="b3_cotacoes",
            modo=params.modo,
        )

        if df_bronze.empty:
            msg = "DataFrame Bronze da B3 está vazio."
            self.logger.emit("WARNING", "B3Cleaner", "LOAD", msg)
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                warnings=[msg],
                error=msg,
            )

        df = df_bronze.copy()

        # 2. Padronização de Tipos
        if "ticker" in df.columns:
            df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
        else:
            err = "Coluna 'ticker' ausente no Bronze B3."
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=err)

        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"], errors="coerce")
        else:
            err = "Coluna 'data' ausente no Bronze B3."
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=err)

        for price_col in ["open", "high", "low", "close"]:
            if price_col in df.columns:
                df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
            else:
                err = f"Coluna '{price_col}' ausente no Bronze B3."
                return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=err)

        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")
        else:
            df["volume"] = pd.Series(dtype="Int64")

        # 3. Higienização: remover linhas sem data, ticker ou com close <= 0 / nulo
        invalid_close_mask = df["close"].isna() | (df["close"] <= 0) | df["data"].isna() | df["ticker"].isna()
        dropped_invalid = invalid_close_mask.sum()
        if dropped_invalid > 0:
            df = df[~invalid_close_mask].copy()
            msg_close = f"Descartadas {dropped_invalid} linhas sem 'close', 'data', 'ticker' ou com 'close' <= 0."
            self.logger.emit("WARNING", "B3Cleaner", "SANITY", msg_close)
            warnings.append(msg_close)

        # Remover duplicatas (ticker, data)
        duplicates_count = df.duplicated(subset=["ticker", "data"]).sum()
        if duplicates_count > 0:
            df = df.drop_duplicates(subset=["ticker", "data"], keep="last").copy()
            msg_dup = f"Removidas {duplicates_count} duplicatas por (ticker, data)."
            self.logger.emit("WARNING", "B3Cleaner", "SANITY", msg_dup)
            warnings.append(msg_dup)

        # Ordenação
        if not df.empty:
            df = df.sort_values(by=["ticker", "data"]).reset_index(drop=True)

        # 4. Regras de Consistência e Sinalização (flag_qualidade)
        tol = 1e-4
        extreme_return_threshold = getattr(settings, "B3_EXTREME_RETURN_THRESHOLD", 0.30)

        flags_list: List[List[str]] = [[] for _ in range(len(df))]

        # Cálculo de retorno diário simples para checagem de evento extremo
        df["_close_prev"] = df.groupby("ticker")["close"].shift(1)
        df["_retorno_temp"] = (df["close"] - df["_close_prev"]) / df["_close_prev"]

        ohlc_issues = 0
        volume_issues = 0
        extreme_returns = 0

        for idx in range(len(df)):
            row = df.iloc[idx]
            row_flags = []

            # Inconsistência OHLC
            max_ohl = max(row["open"], row["close"], row["low"])
            min_ohc = min(row["open"], row["close"], row["high"])

            if row["high"] < (max_ohl - tol) or row["low"] > (min_ohc + tol):
                row_flags.append("OHLC_INVALIDO")
                ohlc_issues += 1

            # Volume
            if pd.notna(row["volume"]):
                if row["volume"] < 0:
                    row_flags.append("VOLUME_NEGATIVO")
                    volume_issues += 1
                elif row["volume"] == 0:
                    row_flags.append("VOLUME_ZERO")
                    volume_issues += 1

            # Retorno diário extremo
            ret_val = row["_retorno_temp"]
            if pd.notna(ret_val) and abs(ret_val) > extreme_return_threshold:
                row_flags.append("RETORNO_EXTREMO")
                extreme_returns += 1

            flags_list[idx] = row_flags

        df["flag_qualidade"] = [",".join(f) if f else "OK" for f in flags_list]

        df.drop(columns=["_close_prev", "_retorno_temp"], inplace=True)

        if ohlc_issues > 0:
            msg_ohlc = f"Sinalizadas {ohlc_issues} linhas com inconsistência em OHLC."
            self.logger.emit("WARNING", "B3Cleaner", "CONSISTENCY", msg_ohlc)
            warnings.append(msg_ohlc)

        if volume_issues > 0:
            msg_vol = f"Sinalizadas {volume_issues} linhas com volume zero ou negativo."
            self.logger.emit("WARNING", "B3Cleaner", "CONSISTENCY", msg_vol)
            warnings.append(msg_vol)

        if extreme_returns > 0:
            msg_ret = f"Sinalizadas {extreme_returns} linhas com retorno diário superior a ±{int(extreme_return_threshold * 100)}%."
            self.logger.emit("WARNING", "B3Cleaner", "CONSISTENCY", msg_ret)
            warnings.append(msg_ret)

        # 5. Relatório de Cobertura por Ticker
        expected_tickers = set(params.tickers)
        processed_tickers = set(df["ticker"].unique()) if not df.empty else set()

        missing_tickers = expected_tickers - processed_tickers
        if missing_tickers:
            msg_missing = f"Tickers solicitados sem dados na Prata: {sorted(list(missing_tickers))}"
            self.logger.emit("WARNING", "B3Cleaner", "COVERAGE", msg_missing)
            warnings.append(msg_missing)

        for tkr, df_tkr in df.groupby("ticker"):
            min_dt = df_tkr["data"].min().strftime("%Y-%m-%d")
            max_dt = df_tkr["data"].max().strftime("%Y-%m-%d")
            count_pregoes = len(df_tkr)

            self.logger.emit(
                "INFO",
                "B3Cleaner",
                "COVERAGE",
                f"Ticker {tkr}: {count_pregoes} pregões de {min_dt} até {max_dt}",
            )

            if count_pregoes < 50:
                msg_low_cov = f"Ticker {tkr} possui cobertura baixa ({count_pregoes} pregões)."
                self.logger.emit("WARNING", "B3Cleaner", "COVERAGE", msg_low_cov)
                warnings.append(msg_low_cov)

        # 6. Persistência na Prata
        cols_to_save = ["ticker", "data", "open", "high", "low", "close", "volume", "flag_qualidade"]
        if "_ingest_ts" in df.columns:
            cols_to_save.append("_ingest_ts")
        if "_run_id" in df.columns:
            cols_to_save.append("_run_id")

        save_res = self.persistence.save(
            layer="silver",
            name="b3_cotacoes",
            df=df[cols_to_save],
            partition_cols=["ticker"],
            modo=params.modo,
        )

        self.logger.emit(
            "INFO",
            "B3Cleaner",
            "CLEAN_SUCCESS",
            f"Prata B3 gravada em {save_res['parquet_path']} ({save_res['rows']} linhas)",
        )

        return StepResult(
            step_id=step_id,
            ok=True,
            rows=len(df),
            paths=[save_res["parquet_path"]],
            warnings=warnings,
        )