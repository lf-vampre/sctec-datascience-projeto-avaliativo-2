"""Módulo de persistência unificada (Parquet + Neon) com suporte a manifest, pushdown e relatório de saúde."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from sqlalchemy import text

from src.utils import db, paths

ALLOWED_LAYERS: Set[str] = {"bronze", "silver", "gold"}

GOLD_TABLES: List[str] = [
    "dim_tempo",
    "dim_empresa",
    "dim_indicador",
    "fato_macro",
    "fato_cotacoes",
    "fato_demonstrativos",
]


class Persistence:
    """Gerenciador de persistência de dados em Parquet local e Neon PostgreSQL com resiliência e manifest."""

    def __init__(self) -> None:
        pass

    def _validate_layer_and_name(self, layer: str, name: str) -> None:
        """Valida whitelist de schemas/camadas e nomes de tabela contra SQL Injection."""
        if layer not in ALLOWED_LAYERS:
            raise ValueError(f"Camada inválida '{layer}'. Permitidas: {ALLOWED_LAYERS}")
        if not name.isidentifier():
            raise ValueError(f"Nome de tabela/arquivo inválido '{name}'. Devem ser identificadores SQL válidos.")

    def _validate_columns(self, columns: Optional[List[str]]) -> None:
        """Garante que todas as colunas solicitadas sejam identificadores válidos."""
        if columns:
            for col in columns:
                if not col.isidentifier():
                    raise ValueError(f"Nome de coluna inválido '{col}'.")

    def _get_base_dir(self, modo: str) -> Path:
        """Retorna o diretório base respeitando o modo (sandbox vs producao)."""
        return paths.SANDBOX_DIR if modo == "sandbox" else paths.DATA_DIR

    def _get_parquet_path(self, layer: str, name: str, modo: str) -> Path:
        """Retorna o caminho do arquivo Parquet dependendo do modo."""
        layer_dir = self._get_base_dir(modo) / layer
        layer_dir.mkdir(parents=True, exist_ok=True)
        return layer_dir / f"{name}.parquet"

    def _get_manifest_path(self, modo: str) -> Path:
        """Retorna o caminho do arquivo _manifest.json da camada Ouro."""
        gold_dir = self._get_base_dir(modo) / "gold"
        gold_dir.mkdir(parents=True, exist_ok=True)
        return gold_dir / "_manifest.json"

    def _count_parquet_rows(self, file_path: Path) -> int:
        """Total real de linhas do Parquet (após upsert), via metadados."""
        try:
            return pq.read_metadata(file_path).num_rows if file_path.exists() else 0
        except Exception:
            return 0

    def _update_manifest(self, name: str, rows: int, neon_ok: bool, modo: str) -> None:
        """Atualiza atômica e thread-safe o arquivo _manifest.json da Ouro."""
        manifest_path = self._get_manifest_path(modo)
        manifest_data: Dict[str, Any] = {}

        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception:
                manifest_data = {}

        manifest_data[name] = {
            "linhas": rows,
            "run_id": str(uuid.uuid4()),
            "atualizado_em": datetime.now().isoformat(),
            "neon_ok": neon_ok,
        }

        temp_manifest = manifest_path.with_suffix(".json.tmp")
        with open(temp_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        temp_manifest.replace(manifest_path)

    def _upsert_parquet(
        self, file_path: Path, new_df: pd.DataFrame, partition_cols: Optional[List[str]], layer: str
    ) -> None:
        """Realiza o upsert por partição em arquivo Parquet com escrita atômica via arquivo temporário."""
        compression = "zstd" if layer == "gold" else "snappy"

        if file_path.exists() and partition_cols:
            try:
                existing_df = pd.read_parquet(file_path)
                keys_to_remove = new_df[partition_cols].drop_duplicates()

                cond = pd.Series(True, index=existing_df.index)
                for _, row in keys_to_remove.iterrows():
                    match_row = pd.Series(True, index=existing_df.index)
                    for col in partition_cols:
                        match_row &= existing_df[col] == row[col]
                    cond &= ~match_row

                filtered_existing = existing_df[cond]
                final_df = pd.concat([filtered_existing, new_df], ignore_index=True)
            except Exception:
                final_df = new_df
        else:
            final_df = new_df

        temp_path = file_path.with_suffix(".parquet.tmp")
        final_df.to_parquet(temp_path, index=False, engine="pyarrow", compression=compression)
        temp_path.replace(file_path)

    # Em Persistence._upsert_neon, substituir o método por:

    def _upsert_neon(
        self, layer: str, name: str, df: pd.DataFrame, partition_cols: Optional[List[str]]
    ) -> bool:
        """Executa upsert por partição ou carga completa (para dimensões) no Neon em uma transação."""
        engine = db.get_engine()
        if engine is None:
            return False

        with engine.begin() as conn:
            df.head(0).to_sql(name=name, schema=layer, con=conn, if_exists="append", index=False)

            if partition_cols and len(df) > 0:
                partition_keys = df[partition_cols].drop_duplicates().to_dict(orient="records")
                for key_dict in partition_keys:
                    where_clauses = [f'"{col}" = :{col}' for col in key_dict.keys()]
                    where_str = " AND ".join(where_clauses)
                    delete_sql = text(f'DELETE FROM "{layer}"."{name}" WHERE {where_str}')
                    conn.execute(delete_sql, key_dict)
            else:
                # Se não há colunas de partição (caso de dimensões), faz limpa e insere (full refresh)
                conn.execute(text(f'DELETE FROM "{layer}"."{name}"'))

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
        """Salva o DataFrame em Parquet e/ou Neon com suporte a upsert e manifest de auditoria."""
        self._validate_layer_and_name(layer, name)

        if df.empty:
            file_path = self._get_parquet_path(layer, name, modo)
            if layer == "gold":
                self._update_manifest(name, self._count_parquet_rows(file_path), False, modo)
            return {"parquet_path": str(file_path), "rows": 0, "neon_ok": False, "warning": "DataFrame vazio"}

        save_df = df.copy()

        if layer in {"bronze", "silver"}:
            if "_ingest_ts" not in save_df.columns:
                save_df["_ingest_ts"] = datetime.now()
            if "_run_id" not in save_df.columns:
                save_df["_run_id"] = str(uuid.uuid4())

        file_path = self._get_parquet_path(layer, name, modo)
        self._upsert_parquet(file_path, save_df, partition_cols, layer)

        neon_ok = False
        warning = None

        if modo == "producao":
            try:
                if db.is_available():
                    neon_ok = self._upsert_neon(layer, name, save_df, partition_cols)
                else:
                    warning = "Neon indisponível no momento. Salvo apenas em Parquet."
            except Exception as e:
                neon_ok = False
                warning = f"Falha na gravação Neon: {str(e)}"

        if layer == "gold":
            self._update_manifest(name, self._count_parquet_rows(file_path), neon_ok, modo)

        return {
            "parquet_path": str(file_path),
            "rows": len(save_df),
            "neon_ok": neon_ok,
            "warning": warning,
        }

    def _build_pyarrow_filter(
        self, filters: Optional[Union[Dict[str, Any], List[Tuple[str, str, Any]]]]
    ) -> Optional[Any]:
        """Converte dicionário ou lista de tuplas em expressão de filtro PyArrow."""
        if not filters:
            return None

        expressions = []

        if isinstance(filters, dict):
            for col, val in filters.items():
                if not col.isidentifier():
                    raise ValueError(f"Filtro com nome de coluna inválido '{col}'.")
                field_expr = ds.field(col)
                if isinstance(val, (list, tuple, set)):
                    expressions.append(field_expr.isin(list(val)))
                else:
                    expressions.append(field_expr == val)
        elif isinstance(filters, list):
            for item in filters:
                col, op, val = item
                if not col.isidentifier():
                    raise ValueError(f"Filtro com nome de coluna inválido '{col}'.")
                field_expr = ds.field(col)
                if op == "=":
                    expressions.append(field_expr == val)
                elif op in ("in", "IN"):
                    expressions.append(field_expr.isin(list(val)))
                elif op == ">=":
                    expressions.append(field_expr >= val)
                elif op == "<=":
                    expressions.append(field_expr <= val)
                elif op == ">":
                    expressions.append(field_expr > val)
                elif op == "<":
                    expressions.append(field_expr < val)

        if not expressions:
            return None

        combined = expressions[0]
        for expr in expressions[1:]:
            combined = combined & expr
        return combined

    def _build_sql_where(
        self, filters: Optional[Union[Dict[str, Any], List[Tuple[str, str, Any]]]]
    ) -> Tuple[str, Dict[str, Any]]:
        """Gera cláusula WHERE parametrizada contra SQL Injection."""
        if not filters:
            return "", {}

        clauses = []
        params: Dict[str, Any] = {}
        param_idx = 0

        if isinstance(filters, dict):
            for col, val in filters.items():
                if not col.isidentifier():
                    raise ValueError(f"Filtro com nome de coluna inválido '{col}'.")
                param_name = f"p_{param_idx}"
                param_idx += 1
                if isinstance(val, (list, tuple, set)):
                    clauses.append(f'"{col}" IN :{param_name}')
                    params[param_name] = tuple(val)
                else:
                    clauses.append(f'"{col}" = :{param_name}')
                    params[param_name] = val
        elif isinstance(filters, list):
            for col, op, val in filters:
                if not col.isidentifier():
                    raise ValueError(f"Filtro com nome de coluna inválido '{col}'.")
                param_name = f"p_{param_idx}"
                param_idx += 1
                op_upper = op.upper()
                if op_upper == "IN":
                    clauses.append(f'"{col}" IN :{param_name}')
                    params[param_name] = tuple(val)
                elif op_upper in ("=", ">=", "<=", ">", "<"):
                    clauses.append(f'"{col}" {op_upper} :{param_name}')
                    params[param_name] = val

        if not clauses:
            return "", {}

        return " WHERE " + " AND ".join(clauses), params

    def _validate_filters(
        self, filters: Optional[Union[Dict[str, Any], List[Tuple[str, str, Any]]]]
    ) -> None:
        """Valida nomes de colunas nos filtros contra SQL Injection / identificadores inválidos."""
        if not filters:
            return
        if isinstance(filters, dict):
            for col in filters.keys():
                if not col.isidentifier():
                    raise ValueError(f"Filtro com nome de coluna inválido '{col}'.")
        elif isinstance(filters, list):
            for item in filters:
                col = item[0]
                if not col.isidentifier():
                    raise ValueError(f"Filtro com nome de coluna inválido '{col}'.")

    def load(
        self,
        layer: str,
        name: str,
        filters: Optional[Union[Dict[str, Any], List[Tuple[str, str, Any]]]] = None,
        columns: Optional[List[str]] = None,
        modo: str = "producao",
    ) -> pd.DataFrame:
        """Carrega os dados do Neon (fallback Parquet em produção) ou estritamente Parquet no modo sandbox."""
        self._validate_layer_and_name(layer, name)
        self._validate_columns(columns)
        self._validate_filters(filters)

        file_path = self._get_parquet_path(layer, name, modo)

        if modo == "sandbox":
            if file_path.exists():
                pa_filter = self._build_pyarrow_filter(filters)
                dataset = ds.dataset(file_path, format="parquet")
                table = dataset.to_table(columns=columns, filter=pa_filter)
                df = table.to_pandas()
                df.attrs["fonte"] = "parquet_sandbox"
                return df
            df = pd.DataFrame()
            df.attrs["fonte"] = "empty"
            return df

        if db.is_available():
            try:
                engine = db.get_engine()
                if engine is not None:
                    cols_sql = ", ".join([f'"{c}"' for c in columns]) if columns else "*"
                    where_sql, sql_params = self._build_sql_where(filters)
                    query = text(f'SELECT {cols_sql} FROM "{layer}"."{name}"{where_sql}')
                    df = pd.read_sql(query, con=engine, params=sql_params)
                    df.attrs["fonte"] = "neon"
                    return df
            except Exception:
                pass

        if file_path.exists():
            pa_filter = self._build_pyarrow_filter(filters)
            dataset = ds.dataset(file_path, format="parquet")
            table = dataset.to_table(columns=columns, filter=pa_filter)
            df = table.to_pandas()
            df.attrs["fonte"] = "parquet"
            return df

        df = pd.DataFrame()
        df.attrs["fonte"] = "empty"
        return df

    def health_report(self, modo: str = "producao") -> Dict[str, Any]:
        """Gera relatório de integridade e auditoria para as tabelas da Ouro."""
        manifest_path = self._get_manifest_path(modo)
        manifest_data: Dict[str, Any] = {}

        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception:
                manifest_data = {}

        report: Dict[str, Any] = {}

        for table in GOLD_TABLES:
            file_path = self._get_parquet_path("gold", table, modo)
            parquet_rows = 0
            if file_path.exists():
                try:
                    parquet_rows = pq.read_metadata(file_path).num_rows
                except Exception:
                    parquet_rows = 0

            neon_rows: Optional[int] = None
            if modo == "producao" and db.is_available():
                try:
                    engine = db.get_engine()
                    if engine is not None:
                        with engine.connect() as conn:
                            res = conn.execute(text(f'SELECT COUNT(*) FROM "gold"."{table}"'))
                            neon_rows = res.scalar()
                except Exception:
                    neon_rows = None

            table_manifest = manifest_data.get(table, {})
            manifest_rows = table_manifest.get("linhas", 0)
            atualizado_em = table_manifest.get("atualizado_em")

            fonte_ativa = "sandbox"
            if modo == "producao":
                fonte_ativa = "neon" if neon_rows is not None else "parquet"

            divergencia = False
            if modo == "producao" and neon_rows is not None:
                if neon_rows != parquet_rows or parquet_rows != manifest_rows:
                    divergencia = True

            report[table] = {
                "linhas_parquet": parquet_rows,
                "linhas_neon": neon_rows,
                "linhas_manifest": manifest_rows,
                "atualizado_em": atualizado_em,
                "fonte_ativa": fonte_ativa,
                "divergencia": divergencia,
            }

        return report