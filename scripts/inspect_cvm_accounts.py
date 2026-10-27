import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.etl.warehouse.persistence import Persistence

p = Persistence()
tables = ["cvm_dre", "cvm_bpa", "cvm_bpp"]

for tb in tables:
    df = p.load(layer="bronze", name=tb, modo="sandbox")
    if df.empty:
        df = p.load(layer="bronze", name=tb, modo="producao")

    print(f"\n=== Tabela Bronze: {tb} ===")
    if df.empty:
        print("Vazia ou não encontrada.")
        continue

    df.columns = [c.upper() for c in df.columns]
    cols = [c for c in ["CD_CVM", "CD_CONTA", "DS_CONTA", "ST_CONTA_FIXA"] if c in df.columns]

    # Amostra das contas principais
    sample = df[cols].drop_duplicates().sort_values(by="CD_CONTA")
    print(sample.head(30).to_string(index=False))