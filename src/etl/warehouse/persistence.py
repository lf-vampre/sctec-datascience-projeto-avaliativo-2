"""Módulo de persistência unificada (Parquet + Neon) com suporte a upsert por partição."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import text

from src.utils import db, paths

ALLOWED_LAYERS: Set[str] = {"bronze", "silver", "gold"}


class Persistence:
    """Gerenciador de persistência de dados em Parquet local e Neon PostgreSQL."""

    def __init__(self) -> None:
        pass

    def _validate_layer_and_name(self, layer: str, name: str) -> None:
        """Valida whitelist de schemas/camadas e nomes de tabela contra SQL Injection."""
        if layer not in ALLOWED_LAYERS:
            raise ValueError(f"Camada inválida '{layer}'. Permitidas: {ALLOWED_LAYERS}")
        if not name.isidentifier():
            raise ValueError(f"Nome de tabela/arquivo inválido '{name}'. Devem ser identificadores SQL válidos.")

    def _get_parquet_path(self, layer: str, name: str, modo: str) -> Path:
        """Retorna o caminho do arquivo Parquet dependendo do modo (sandbox vs producao)."""
        base_dir = paths.SANDBOX_DIR if modo == "sandbox" else paths.DATA_DIR
        layer_dir = base_dir / layer
        layer_dir.mkdir(parents=True, exist_ok=True)
        return layer_dir / f"{name}.parquet"

    def _upsert_parquet(self, file_path: Path, new_df: pd.DataFrame, partition_cols: Optional[List[str]]) -> None:
        """Realiza o upsert por partição em arquivo Parquet com escrita atômica via arquivo temporário."""
        if file_path.exists() and partition_cols:
            try:
                existing_df = pd.read_parquet(file_path)
                # Identifica chaves de partição presentes no novo DataFrame
                keys_to_remove = new_df[partition_cols].drop_duplicates()
                
                # Aplica filtro para remover partições que serão substituídas
                cond = pd.Series(True, index=existing_df.index)
                for _, row in keys_to_remove.iterrows():
                    match_row = pd.Series(True, index=existing_df.index)
                    for col in partition_cols:
                        match_row &= (existing_df[col] == row[col])
                    cond &= ~match_row
                
                filtered_existing = existing_df[cond]
                final_df = pd.concat([filtered_existing, new_df], ignore_index=True)
            except Exception:
                final_df = new_df
        else:
            final_df = new_df

        # Escrita atômica: salva em arquivo temporário e substitui
        temp_path = file_path.with_suffix(".parquet.tmp")
        final_df.to_parquet(temp_path, index=False, engine="pyarrow")
        temp_path.replace(file_path)

    def _upsert_neon(
        self, layer: str, name: str, df: pd.DataFrame, partition_cols: Optional[List[str]]
    ) -> bool:
        """Executa upsert por partição no Neon PostgreSQL em uma única transação."""
        engine = db.get_engine()
        if engine is None:
            return False

        with engine.begin() as conn:
            # Cria a tabela se não existir
            df.head(0).to_sql(name=name, schema=layer, con=conn, if_exists="append", index=False)

            if partition_cols and len(df) > 0:
                # Remove partições existentes presentes no DataFrame novo
                partition_keys = df[partition_cols].drop_duplicates().to_dict(orient="records")
                for key_dict in partition_keys:
                    where_clauses = [f'"{col}" = :{col}' for col in key_dict.keys()]
                    where_str = " AND ".join(where_clauses)
                    delete_sql = text(f'DELETE FROM "{layer}"."{name}" WHERE {where_str}')
                    conn.execute(delete_sql, key_dict)

            # Insere os novos dados
            df.to_sql(name=name, schema=layer, con=conn, if_exists="append", index=False)

        return True

    def save(
        self,
        layer: str,
        name: str,
        df: pd.DataFrame,
        partition_cols: Optional[List[str]] = None,
        modo: str = "producao",
    ) -> Dict[str, Any]:
        """Salva o DataFrame em Parquet e/ou Neon com suporte a upsert e auditoria."""
        self._validate_layer_and_name(layer, name)
        
        if df.empty:
            file_path = self._get_parquet_path(layer, name, modo)
            return {"parquet_path": str(file_path), "rows": 0, "neon_ok": False, "warning": "DataFrame vazio"}

        save_df = df.copy()

        # Adiciona colunas de auditoria para bronze e silver
        if layer in {"bronze", "silver"}:
            if "_ingest_ts" not in save_df.columns:
                save_df["_ingest_ts"] = datetime.now()
            if "_run_id" not in save_df.columns:
                save_df["_run_id"] = str(uuid.uuid4())

        # 1. Gravação local Parquet
        file_path = self._get_parquet_path(layer, name, modo)
        self._upsert_parquet(file_path, save_df, partition_cols)

        neon_ok = False
        warning = None

        # 2. Gravação Neon (apenas em modo producao)
        if modo == "producao":
            try:
                if db.is_available():
                    neon_ok = self._upsert_neon(layer, name, save_df, partition_cols)
                else:
                    warning = "Neon indisponível no momento. Salvo apenas em Parquet."
            except Exception as e:
                neon_ok = False
                warning = f"Falha na gravação Neon: {str(e)}"

        return {
            "parquet_path": str(file_path),
            "rows": len(save_df),
            "neon_ok": neon_ok,
            "warning": warning,
        }

    def load(
        self,
        layer: str,
        name: str,
        filters: Optional[List[Tuple[str, str, Any]]] = None,
        columns: Optional[List[str]] = None,
        modo: str = "producao",
    ) -> pd.DataFrame:
        """Carrega os dados do Neon (fallback Parquet em produção) ou estritamente Parquet no modo sandbox."""
        self._validate_layer_and_name(layer, name)

        file_path = self._get_parquet_path(layer, name, modo)

        # Em modo sandbox, lê unicamente de _sandbox
        if modo == "sandbox":
            if file_path.exists():
                df = pd.read_parquet(file_path, columns=columns)
                df.attrs["fonte"] = "parquet_sandbox"
                return df
            df = pd.DataFrame()
            df.attrs["fonte"] = "empty"
            return df

        # Modo produção: tenta Neon
        if db.is_available():
            try:
                engine = db.get_engine()
                if engine is not None:
                    cols_sql = ", ".join([f'"{c}"' for c in columns]) if columns else "*"
                    query = f'SELECT {cols_sql} FROM "{layer}"."{name}"'
                    df = pd.read_sql(query, con=engine)
                    df.attrs["fonte"] = "neon"
                    return df
            except Exception:
                pass

        # Fallback Parquet local
        if file_path.exists():
            df = pd.read_parquet(file_path, columns=columns)
            df.attrs["fonte"] = "parquet"
            return df

        df = pd.DataFrame()
        df.attrs["fonte"] = "empty"
        return df