"""Extrator de dados cadastrais das companhias abertas junto à CVM."""

import gc
import time
from typing import Dict, List, Optional, Set
import pandas as pd
import requests

from src.config import settings
from src.config import universe
from src.etl.base import BaseExtractor, PipelineLogger, bronze_is_fresh, get_layer_path
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams, StepResult


class CadastroExtractor(BaseExtractor):
    """Extrator do cadastro geral de companhias abertas da CVM para a camada Bronze."""

    def __init__(self, logger: PipelineLogger, storage_writer: Optional[Persistence] = None) -> None:
        super().__init__(logger, storage_writer)
        self.persistence = storage_writer or Persistence()

    def _get_target_cvm_codes(self, params_tickers: List[str]) -> Dict[str, int]:
        """Obtém o mapeamento ticker -> CD_CVM considerando dataclasses CompanyInfo ou dicionários em universe."""
        ticker_map: Dict[str, int] = {}

        if hasattr(universe, "COMPANIES"):
            comps = getattr(universe, "COMPANIES")
            for t, info in comps.items():
                if hasattr(info, "cd_cvm"):
                    ticker_map[t.upper()] = int(info.cd_cvm)
                elif isinstance(info, dict) and "cd_cvm" in info:
                    ticker_map[t.upper()] = int(info["cd_cvm"])

        if not ticker_map and hasattr(universe, "TICKER_TO_CVM"):
            raw_map = getattr(universe, "TICKER_TO_CVM")
            ticker_map = {t.upper(): int(v) for t, v in raw_map.items()}

        if params_tickers:
            req_tickers = {t.upper() for t in params_tickers}
            return {t: cd for t, cd in ticker_map.items() if t in req_tickers}
        return ticker_map

    def extract(self, params: PipelineParams) -> StepResult:
        """Baixa o cadastro de companhias abertas da CVM, filtra o universo e persiste na camada Bronze."""
        step_id = "extract_cadastro_cvm"
        warnings: List[str] = []

        bronze_dir = get_layer_path(params, "bronze")
        target_file = bronze_dir / "cvm_cadastro.parquet"

        # Verificação do TTL do arquivo Bronze
        if bronze_is_fresh(target_file, settings.BRONZE_TTL_DAYS):
            self.logger.emit(
                "INFO",
                "CadastroExtractor",
                "CACHE",
                f"Arquivo Bronze recente encontrado em {target_file}. Reutilizando dados.",
            )
            cached_df = self.persistence.load("bronze", "cvm_cadastro", modo=params.modo)
            return StepResult(
                step_id=step_id,
                ok=True,
                rows=len(cached_df),
                paths=[str(target_file)],
                warnings=["Reutilizado do cache Bronze (TTL)"],
            )

        target_map = self._get_target_cvm_codes(params.tickers)
        target_cvm_codes: Set[int] = set(target_map.values())

        if not target_cvm_codes:
            msg = "Nenhum código CD_CVM localizado para os tickers fornecidos."
            self.logger.emit("WARNING", "CadastroExtractor", "UNIVERSE", msg)
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                error=msg,
            )

        url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
        self.logger.emit("INFO", "CadastroExtractor", "HTTP", f"Baixando cadastro CVM de {url}")

        df_raw: Optional[pd.DataFrame] = None
        headers = {"User-Agent": "Mozilla/5.0 (DataOps-Pipeline)"}

        for attempt in range(1, 4):
            try:
                res = requests.get(url, headers=headers, timeout=20)
                if res.status_code == 200:
                    # Converte o conteúdo CSV utilizando encoding CP1252 e separador ponto-e-vírgula
                    from io import BytesIO
                    df_raw = pd.read_csv(
                        BytesIO(res.content),
                        sep=";",
                        encoding="cp1252",
                        dtype=str,
                    )
                    break
                else:
                    res.raise_for_status()
            except Exception as e:
                self.logger.emit(
                    "WARNING",
                    "CadastroExtractor",
                    "RETRY",
                    f"Tentativa {attempt} falhou ao baixar cadastro CVM: {str(e)}",
                )
                time.sleep(1.0 * attempt)
            finally:
                if "res" in locals():
                    del res

        if df_raw is None or df_raw.empty:
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                error="Não foi possível baixar o cadastro de companhias da CVM.",
            )

        # Padroniza nomes das colunas
        df_raw.columns = [col.strip().upper() for col in df_raw.columns]

        # Garantia de presença da coluna CD_CVM e conversão para inteiro para comparação segura
        if "CD_CVM" not in df_raw.columns:
            return StepResult(
                step_id=step_id,
                ok=False,
                rows=0,
                paths=[],
                error="Coluna CD_CVM não encontrada no arquivo baixado da CVM.",
            )

        # Normaliza código CVM para comparação
        df_raw["CD_CVM_INT"] = pd.to_numeric(df_raw["CD_CVM"], errors="coerce")
        df_filtered = df_raw[df_raw["CD_CVM_INT"].isin(target_cvm_codes)].copy()
        df_filtered.drop(columns=["CD_CVM_INT"], inplace=True)

        # Validação do Universo e Geração de Avisos
        encontrados_cvm = set(pd.to_numeric(df_filtered["CD_CVM"], errors="coerce").dropna().astype(int))
        for ticker, cd in target_map.items():
            if cd not in encontrados_cvm:
                msg = f"Ticker {ticker} (CD_CVM {cd}) não foi encontrado no cadastro da CVM."
                warnings.append(msg)
                self.logger.emit("WARNING", "CadastroExtractor", "VALIDATION", msg)

        # Checagem de duplicações de CD_CVM
        duplicados = df_filtered[df_filtered["CD_CVM"].duplicated(keep=False)]
        if not duplicados.empty:
            cds_dup = duplicados["CD_CVM"].unique().tolist()
            msg = f"CD_CVMs duplicados encontrados no cadastro CVM: {cds_dup}"
            warnings.append(msg)
            self.logger.emit("WARNING", "CadastroExtractor", "VALIDATION", msg)

        # Checagem de companhias com situação cancelada/inativa
        if "SIT" in df_filtered.columns:
            canceladas = df_filtered[df_filtered["SIT"].str.contains("CANCELAD|INATIV", case=False, na=False)]
            for _, row in canceladas.iterrows():
                msg = f"Companhia {row.get('DENOM_SOCIAL', '')} (CD_CVM {row.get('CD_CVM')}) está com situação '{row.get('SIT')}'."
                warnings.append(msg)
                self.logger.emit("WARNING", "CadastroExtractor", "VALIDATION", msg)

        # Seleção das colunas relevantes mantendo nomes originais
        cols_interesse = [
            "CNPJ_CIA",
            "DENOM_SOCIAL",
            "DENOM_COMERC",
            "CD_CVM",
            "SIT",
            "SETOR_ATIV",
            "TP_MERC",
            "CATEG_REG",
        ]
        cols_presentes = [c for c in cols_interesse if c in df_filtered.columns]
        df_final = df_filtered[cols_presentes].copy()

        # Liberação de memória
        del df_raw
        del df_filtered
        gc.collect()

        save_res = self.persistence.save(
            layer="bronze",
            name="cvm_cadastro",
            df=df_final,
            partition_cols=["cd_cvm" if "cd_cvm" in df_final.columns else "CD_CVM"],
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