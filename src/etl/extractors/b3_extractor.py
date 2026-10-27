"""Extrator de cotações históricas da B3 via Yahoo Finance (yfinance)."""

import gc
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd
import requests
import yfinance as yf

from src.config import settings
from src.etl.base import BaseExtractor, PipelineLogger, bronze_is_fresh, get_layer_path
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


def _adjust_end_date(date_str: str) -> str:
    """Ajusta a data final para torná-la inclusiva na consulta do yfinance."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt_end = dt + timedelta(days=1)
    return dt_end.strftime("%Y-%m-%d")


class B3Extractor(BaseExtractor):
    """Extrator de cotações diárias da B3 para a camada Bronze."""

    def __init__(self, logger: PipelineLogger, storage_writer: Optional[Persistence] = None) -> None:
        super().__init__(logger, storage_writer)
        self.persistence = storage_writer or Persistence()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def extract(self, params: PipelineParams) -> StepResult:
        """Extrai cotações da B3 via yfinance em lote e persiste em formato longo."""
        step_id = "extract_b3_cotacoes"
        warnings: List[str] = []

        bronze_dir = get_layer_path(params, "bronze")
        target_file = bronze_dir / "b3_cotacoes.parquet"

        # Reaproveitamento por TTL
        if bronze_is_fresh(target_file, settings.BRONZE_TTL_DAYS):
            self.logger.emit(
                "INFO",
                "B3Extractor",
                "CACHE",
                f"Arquivo Bronze recente encontrado em {target_file}. Reutilizando dados.",
            )
            cached_df = self.persistence.load("bronze", "b3_cotacoes", modo=params.modo)
            return StepResult(
                step_id=step_id,
                ok=True,
                rows=len(cached_df),
                paths=[str(target_file)],
                warnings=["Reutilizado do cache Bronze (TTL)"],
            )

        tickers = params.tickers or []
        if not tickers:
            msg = "Nenhum ticker fornecido para extração da B3."
            self.logger.emit("WARNING", "B3Extractor", "UNIVERSE", msg)
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=msg)

        start_date = params.b3_periodo[0]
        end_date_adj = _adjust_end_date(params.b3_periodo[1])
        yf_tickers = [f"{t}.SA" if not t.endswith(".SA") else t for t in tickers]

        self.logger.emit(
            "INFO",
            "B3Extractor",
            "HTTP",
            f"Baixando cotações B3: {tickers} ({start_date} a {params.b3_periodo[1]})",
        )

        try:
            df_raw = yf.download(
                tickers=yf_tickers,
                start=start_date,
                end=end_date_adj,
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                session=self.session,
            )
        except Exception as e:
            msg = f"Falha na consulta ao yfinance: {str(e)}"
            self.logger.emit("ERROR", "B3Extractor", "HTTP", msg)
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=msg)

        if df_raw is None or df_raw.empty:
            msg = "Nenhum dado retornado do yfinance para os tickers informados."
            self.logger.emit("WARNING", "B3Extractor", "HTTP", msg)
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], warnings=warnings, error=msg)

        extracted_dfs: List[pd.DataFrame] = []
        is_multi_index = isinstance(df_raw.columns, pd.MultiIndex)

        for orig_ticker, yf_symbol in zip(tickers, yf_tickers):
            try:
                # Extração por ticker conforme estrutura do MultiIndex (yfinance >= 1.0)
                if is_multi_index:
                    if yf_symbol in df_raw.columns.get_level_values(0):
                        df_t = df_raw[yf_symbol].copy()
                    elif yf_symbol in df_raw.columns.get_level_values(1):
                        df_t = df_raw.xs(yf_symbol, level=1, axis=1).copy()
                    else:
                        df_t = pd.DataFrame()
                else:
                    df_t = df_raw.copy()

                if df_t.empty or df_t.dropna(how="all").empty:
                    msg = f"Ticker {orig_ticker} não retornou dados no período solicitado."
                    warnings.append(msg)
                    self.logger.emit("WARNING", "B3Extractor", "DATA", msg)
                    continue

                df_t = df_t.reset_index()
                df_t.columns = [str(c).lower().replace(" ", "_") for c in df_t.columns]

                # Mapeamento do nome da coluna de data
                date_col = "date" if "date" in df_t.columns else df_t.columns[0]
                df_t.rename(columns={date_col: "data"}, inplace=True)

                df_t["ticker"] = orig_ticker

                if pd.api.types.is_datetime64_any_dtype(df_t["data"]):
                    df_t["data"] = df_t["data"].dt.strftime("%Y-%m-%d")
                else:
                    df_t["data"] = pd.to_datetime(df_t["data"], utc=True).dt.strftime("%Y-%m-%d")

                expected_cols = ["data", "open", "high", "low", "close", "volume", "ticker"]
                cols_to_keep = [c for c in expected_cols if c in df_t.columns]
                df_t = df_t[cols_to_keep]

                # Descarte de linhas sem preço de fechamento
                if "close" in df_t.columns:
                    df_t = df_t.dropna(subset=["close"])

                if not df_t.empty:
                    extracted_dfs.append(df_t)
                else:
                    msg = f"Ticker {orig_ticker} não possui registros com preço de fechamento válido."
                    warnings.append(msg)
                    self.logger.emit("WARNING", "B3Extractor", "DATA", msg)

            except Exception as ex:
                msg = f"Erro ao processar dados de {orig_ticker}: {str(ex)}"
                warnings.append(msg)
                self.logger.emit("ERROR", "B3Extractor", "PARSE", msg)

        del df_raw
        gc.collect()

        if not extracted_dfs:
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                warnings=warnings,
                error="Nenhum dado de cotação foi retornado para os tickers solicitados.",
            )

        final_df = pd.concat(extracted_dfs, ignore_index=True)
        release(extracted_dfs)

        save_res = self.persistence.save(
            layer="bronze",
            name="b3_cotacoes",
            df=final_df,
            partition_cols=["ticker"],
            modo=params.modo,
        )

        if save_res.get("warning"):
            warnings.append(save_res["warning"])

        return StepResult(
            step_id=step_id,
            ok=True,
            rows=save_res["rows"],
            paths=[save_res["parquet_path"]],
            warnings=warnings,
        )