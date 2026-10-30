"""Extrator de demonstrativos financeiros (DFP) da CVM para a camada Bronze."""

import gc
import io
import zipfile
from typing import Dict, List, Optional, Set
import pandas as pd
import requests

from src.config import universe
from src.etl.base import BaseExtractor, PipelineLogger, bronze_cache_status, write_bronze_signature, get_layer_path
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


class CvmExtractor(BaseExtractor):
    """Extrator de DFP (DRE, BPA, BPP) da CVM para a camada Bronze."""

    def __init__(self, logger: PipelineLogger, storage_writer: Optional[Persistence] = None) -> None:
        super().__init__(logger, storage_writer)
        self.persistence = storage_writer or Persistence()

    def _get_target_cd_cvm(self, tickers: List[str]) -> Set[str]:
        """Mapeia os tickers informados para seus respectivos códigos CVM (CD_CVM)."""
        cd_cvm_set: Set[str] = set()
        for t in tickers:
            comp = universe.COMPANIES.get(t)
            if comp:
                cd = getattr(comp, "cd_cvm", None) or getattr(comp, "CD_CVM", None)
                if cd is not None:
                    raw_str = str(cd).strip()
                    cd_cvm_set.add(raw_str)
                    cd_cvm_set.add(raw_str.zfill(6))
                    try:
                        cd_cvm_set.add(str(int(raw_str)))
                    except ValueError:
                        pass
        return cd_cvm_set

    def extract(self, params: PipelineParams) -> StepResult:
        """Baixa demonstrativos anuais da CVM, filtra por CD_CVM e persiste DRE, BPA e BPP."""
        step_id = "extract_cvm_dfp"
        warnings: List[str] = []

        bronze_dir = get_layer_path(params, "bronze")
        target_tables = ["cvm_dre", "cvm_bpa", "cvm_bpp"]
        
        # Verificação do TTL nos arquivos Bronze de destino
        signature = {
            "tickers": sorted(t.upper() for t in (params.tickers or [])),
            "anos": sorted(int(a) for a in (params.cvm_anos or [])),
        }

        all_fresh = True
        motivo = ""
        for table in target_tables:
            fresh, motivo = bronze_cache_status(bronze_dir / f"{table}.parquet", signature)
            if not fresh:
                all_fresh = False
                break

        if all_fresh:
            self.logger.emit("INFO", "CvmExtractor", "CACHE", f"Bronze CVM reutilizado ({motivo}).")
            total_rows = 0
            paths = []
            for table in target_tables:
                df_c = self.persistence.load("bronze", table, modo=params.modo)
                total_rows += len(df_c)
                paths.append(str(bronze_dir / f"{table}.parquet"))

            return StepResult(
                step_id=step_id,
                ok=True,
                rows=total_rows,
                paths=paths,
                warnings=["Reutilizado do cache Bronze (TTL)"],
            )

        self.logger.emit("INFO", "CvmExtractor", "CACHE", f"Bronze CVM não reutilizado: {motivo}.")

        target_cd_cvm = self._get_target_cd_cvm(params.tickers or [])
        if not target_cd_cvm:
            msg = "Nenhum código CVM (CD_CVM) encontrado para os tickers informados."
            self.logger.emit("WARNING", "CvmExtractor", "UNIVERSE", msg)
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                error=msg,
            )

        anos = params.cvm_anos or []
        if not anos:
            msg = "Nenhum ano especificado para extração CVM."
            self.logger.emit("WARNING", "CvmExtractor", "PARAMS", msg)
            return StepResult(step_id=step_id, ok=False, rows=0, paths=[], error=msg)

        extracted_dfs: Dict[str, List[pd.DataFrame]] = {
            "cvm_dre": [],
            "cvm_bpa": [],
            "cvm_bpp": [],
        }

        successful_years = 0

        for ano in anos:
            url = f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip"
            self.logger.emit("INFO", "CvmExtractor", "HTTP", f"Baixando ZIP CVM ano {ano}: {url}")

            try:
                resp = requests.get(url, timeout=60)
                if resp.status_code != 200:
                    msg = f"Download falhou para ano {ano} (HTTP {resp.status_code})."
                    warnings.append(msg)
                    self.logger.emit("WARNING", "CvmExtractor", "HTTP", msg)
                    continue

                zip_content = io.BytesIO(resp.content)
                del resp

                with zipfile.ZipFile(zip_content) as z:
                    file_list = z.namelist()

                    # Padronização de padrões para os relatórios consolidados
                    patterns = {
                        "cvm_dre": "_DRE_con_",
                        "cvm_bpa": "_BPA_con_",
                        "cvm_bpp": "_BPP_con_",
                    }

                    year_got_data = False

                    for table_key, pattern in patterns.items():
                        target_filename = next((f for f in file_list if pattern in f), None)
                        if not target_filename:
                            msg = f"Arquivo {pattern} não encontrado no ZIP do ano {ano}."
                            warnings.append(msg)
                            self.logger.emit("WARNING", "CvmExtractor", "ZIP", msg)
                            continue

                        with z.open(target_filename) as f:
                            df_chunk = pd.read_csv(
                                f,
                                sep=";",
                                encoding="cp1252",
                                dtype=str,
                            )

                            if "CD_CVM" in df_chunk.columns:
                                df_filtered = df_chunk[
                                    df_chunk["CD_CVM"].astype(str).str.strip().isin(target_cd_cvm)
                                ].copy()

                                if not df_filtered.empty:
                                    df_filtered["ano_arquivo"] = str(ano)
                                    extracted_dfs[table_key].append(df_filtered)
                                    year_got_data = True
                            
                            del df_chunk

                del zip_content
                if year_got_data:
                    successful_years += 1

            except Exception as e:
                msg = f"Erro ao processar CVM ano {ano}: {str(e)}"
                warnings.append(msg)
                self.logger.emit("ERROR", "CvmExtractor", "PARSE", msg)
            finally:
                gc.collect()

        if successful_years == 0 or not any(extracted_dfs.values()):
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                warnings=warnings,
                error="Nenhum dado CVM extraído para os anos solicitados.",
            )

        saved_paths: List[str] = []
        total_rows_saved = 0

        # Persistência das três tabelas Bronze
        for table_key in target_tables:
            df_list = extracted_dfs[table_key]
            if df_list:
                df_concat = pd.concat(df_list, ignore_index=True)
                release(df_list)

                save_res = self.persistence.save(
                    layer="bronze",
                    name=table_key,
                    df=df_concat,
                    partition_cols=None,
                    modo=params.modo,
                )

                total_rows_saved += save_res["rows"]
                saved_paths.append(save_res["parquet_path"])

                write_bronze_signature(bronze_dir / f"{table_key}.parquet", signature)

                if save_res.get("warning"):
                    warnings.append(save_res["warning"])
                
                del df_concat
                gc.collect()

        return StepResult(
            step_id=step_id,
            ok=True,
            rows=total_rows_saved,
            paths=saved_paths,
            warnings=warnings,
        )