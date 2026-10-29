"""Testes unitários do módulo de persistência (src/etl/warehouse/persistence.py)."""

from pathlib import Path
import pandas as pd
import pytest
import json

from src.etl.warehouse.persistence import Persistence


def test_parquet_upsert_partition(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("src.utils.paths.SANDBOX_DIR", tmp_path / "data" / "_sandbox")

    p = Persistence()

    # Carga 1: Partição A (serie 1) e B (serie 2)
    df1 = pd.DataFrame({
        "serie_codigo": [1, 2],
        "data": ["2023-01-01", "2023-01-01"],
        "valor": [10.0, 20.0]
    })
    res1 = p.save("bronze", "test_bacen", df1, partition_cols=["serie_codigo"], modo="producao")
    assert res1["rows"] == 2

    # Carga 2: Atualização da Partição A (substitui a serie_codigo 1 e preserva a 2)
    df2 = pd.DataFrame({
        "serie_codigo": [1],
        "data": ["2023-01-01"],
        "valor": [99.0]
    })
    res2 = p.save("bronze", "test_bacen", df2, partition_cols=["serie_codigo"], modo="producao")
    assert res2["rows"] == 1

    loaded = p.load("bronze", "test_bacen", modo="producao")
    assert len(loaded) == 2

    val_p1 = loaded[loaded["serie_codigo"] == 1]["valor"].values[0]
    val_p2 = loaded[loaded["serie_codigo"] == 2]["valor"].values[0]
    assert val_p1 == 99.0
    assert val_p2 == 20.0


def test_sandbox_isolation(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    sandbox_dir = tmp_path / "data" / "_sandbox"
    monkeypatch.setattr("src.utils.paths.DATA_DIR", data_dir)
    monkeypatch.setattr("src.utils.paths.SANDBOX_DIR", sandbox_dir)

    p = Persistence()
    df = pd.DataFrame({"col": [1, 2]})

    res = p.save("bronze", "test_sb", df, modo="sandbox")
    assert "_sandbox" in res["parquet_path"]
    assert res["neon_ok"] is False

    prod_path = data_dir / "bronze" / "test_sb.parquet"
    assert not prod_path.exists()


def test_load_fallback_when_neon_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("src.utils.paths.SANDBOX_DIR", tmp_path / "data" / "_sandbox")
    monkeypatch.setattr("src.utils.db.is_available", lambda: False)

    p = Persistence()
    df = pd.DataFrame({"col": [100]})
    p.save("silver", "test_fallback", df, modo="producao")

    loaded = p.load("silver", "test_fallback", modo="producao")
    assert loaded.attrs.get("fonte") == "parquet"
    assert len(loaded) == 1
    assert loaded["col"].iloc[0] == 100

def test_manifest_registra_total_real_apos_upsert(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("src.utils.paths.SANDBOX_DIR", tmp_path / "data" / "_sandbox")

    p = Persistence()
    p.save("gold", "fato_macro", pd.DataFrame({"sk_tempo": [1, 2], "valor": [1.0, 2.0]}),
           partition_cols=["sk_tempo"], modo="sandbox")
    p.save("gold", "fato_macro", pd.DataFrame({"sk_tempo": [3], "valor": [3.0]}),
           partition_cols=["sk_tempo"], modo="sandbox")

    manifest_path = tmp_path / "data" / "_sandbox" / "gold" / "_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["fato_macro"]["linhas"] == 3  # total real, não as 1 do último save    