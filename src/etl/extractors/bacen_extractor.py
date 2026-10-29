"""Extrator de dados macroeconômicos da API SGS do Banco Central do Brasil (BACEN)."""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import requests

from src.config import settings
from src.etl.base import BaseExtractor, PipelineLogger, bronze_cache_status, write_bronze_signature, get_layer_path
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


def _format_date_bacen(date_str: str) -> str:
    """Converte 'YYYY-MM-DD' para 'DD/MM/YYYY' exigido pela API do BACEN."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%d/%m/%Y")


class BacenExtractor(BaseExtractor):
    """Extrator de séries temporais da API SGS/BACEN para a camada Bronze."""

    def __init__(self, logger: PipelineLogger, storage_writer: Optional[Persistence] = None) -> None:
        super().__init__(logger, storage_writer)
        self.persistence = storage_writer or Persistence()

    def extract(self, params: PipelineParams) -> StepResult:
        """Extrai as 7 séries macroeconômicas do BACEN e salva na camada Bronze."""
        step_id = "extract_bacen"
        warnings: List[str] = []

        # Roteamento do caminho e verificação do TTL do Bronze
        bronze_dir = get_layer_path(params, "bronze")
        target_file = bronze_dir / "bacen_sgs.parquet"

        series_map: Dict[int, str] = getattr(
            settings,
            "BACEN_SERIES",
            {
                432: "SELIC Meta",
                1178: "CDI Efetivo",
                433: "IPCA",
                13522: "IGP-M",
                1: "Câmbio USD",
                24364: "IBC-Br",
                196: "Poupança",
            },
        )

        signature = {
            "periodo": list(params.bacen_periodo),
            "series": sorted(str(k) for k in series_map.keys()),
        }
        reutilizar, motivo = bronze_cache_status(target_file, signature)

        if reutilizar:
            self.logger.emit(
                "INFO", "BacenExtractor", "CACHE",
                f"Bronze reutilizado ({motivo}): {target_file}",
            )
            cached_df = self.persistence.load("bronze", "bacen_sgs", modo=params.modo)
            return StepResult(
                step_id=step_id,
                ok=True,
                rows=len(cached_df),
                paths=[str(target_file)],
                warnings=["Reutilizado do cache Bronze (TTL)"],
            )

        self.logger.emit("INFO", "BacenExtractor", "CACHE", f"Bronze não reutilizado: {motivo}.")

        data_ini_fmt = _format_date_bacen(params.bacen_periodo[0])
        data_fim_fmt = _format_date_bacen(params.bacen_periodo[1])


        all_series_dfs: List[pd.DataFrame] = []
        headers = {"User-Agent": "Mozilla/5.0 (DataOps-Pipeline)"}

        for item_key, item_val in series_map.items():
            if isinstance(item_val, dict):
                cod_serie = item_val.get("sgs_codigo", item_key)
                nome_serie = item_val.get("nome", str(item_key))
            else:
                cod_serie = item_key
                nome_serie = item_val

            url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod_serie}/dados?formato=json&dataInicial={data_ini_fmt}&dataFinal={data_fim_fmt}"
            self.logger.emit("INFO", "BacenExtractor", "HTTP", f"Buscando série {cod_serie} ({nome_serie})")

            success = False
            for attempt in range(1, 4):
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    if res.status_code == 200:
                        payload = res.json()
                        if payload:
                            df_serie = pd.DataFrame(payload)
                            df_serie["serie_codigo"] = cod_serie
                            df_serie["serie_nome"] = nome_serie
                            all_series_dfs.append(df_serie)
                        else:
                            msg = f"Série {cod_serie} ({nome_serie}) retornou lista vazia."
                            self.logger.emit("WARNING", "BacenExtractor", "HTTP", msg)
                            warnings.append(msg)
                        success = True
                        break
                    elif res.status_code in (429, 500, 502, 503, 504):
                        time.sleep(1.0 * attempt)
                    else:
                        res.raise_for_status()
                except Exception as e:
                    self.logger.emit(
                        "WARNING",
                        "BacenExtractor",
                        "RETRY",
                        f"Tentativa {attempt} falhou para série {cod_serie}: {str(e)}",
                    )
                    time.sleep(1.0 * attempt)
                finally:
                    if 'res' in locals():
                        del res

            if not success:
                msg = f"Falha ao obter série {cod_serie} ({nome_serie}) após tentativas."
                self.logger.emit("ERROR", "BacenExtractor", "HTTP", msg)
                warnings.append(msg)

            time.sleep(0.2)  # Pausa respeitosa entre requisições

        if not all_series_dfs:
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                warnings=warnings,
                error="Nenhuma série do BACEN pôde ser obtida.",
            )

        final_df = pd.concat(all_series_dfs, ignore_index=True)
        # Garantir colunas no padrão Bronze cru (strings)
        final_df = final_df[["serie_codigo", "serie_nome", "data", "valor"]]

        save_res = self.persistence.save(
            layer="bronze",
            name="bacen_sgs",
            df=final_df,
            partition_cols=None,
            modo=params.modo,
        )

        if save_res.get("warning"):
            warnings.append(save_res["warning"])

        write_bronze_signature(target_file, signature)

        return StepResult(
            step_id=step_id,
            ok=True,
            rows=save_res["rows"],
            paths=[save_res["parquet_path"]],
            warnings=warnings,
        )