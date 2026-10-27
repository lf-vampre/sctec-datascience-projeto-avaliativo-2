"""Script de execução e validação da carga Prata em modo Produção."""

from pathlib import Path
import pandas as pd

from src.config.universe import COMPANIES
from src.etl.base import PipelineLogger
from src.etl.cleaners.b3_cleaner import B3Cleaner
from src.etl.cleaners.bacen_cleaner import BacenCleaner
from src.etl.cleaners.cvm_cleaner import CvmCleaner
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams
from src.utils.paths import SILVER_DIR


def main() -> None:
    logger = PipelineLogger()
    persistence = Persistence()

    tickers = list(COMPANIES.keys())

    params = PipelineParams(
        tickers=tickers,
        bacen_periodo=("2019-01-01", "2023-12-31"),
        b3_periodo=("2019-01-01", "2024-01-01"),
        cvm_anos=[2019, 2020, 2021, 2022, 2023],
        is_sandbox=False,
    )

    cleaners = [
        ("BacenCleaner", BacenCleaner(logger=logger, storage_writer=persistence)),
        ("B3Cleaner", B3Cleaner(logger=logger, storage_writer=persistence)),
        ("CvmCleaner", CvmCleaner(logger=logger, storage_writer=persistence)),
    ]

    print("=" * 60)
    print("INICIANDO CARGA PRATA (MODO PRODUÇÃO)")
    print(f"Tickers ({len(tickers)}): {tickers}")
    print("=" * 60)

    results = {}
    for name, cleaner in cleaners:
        print(f"\n---> Executando {name}...")
        res = cleaner.clean(params)
        results[name] = res
        print(
            f"Status: {'OK' if res.ok else 'FALHA'} | Linhas: {res.rows} | "
            f"Avisos: {len(res.warnings)} | Erro: {res.error or 'Nenhum'}"
        )
        if res.warnings:
            for w in res.warnings:
                print(f"   [AVISO] {w}")

    print("\n" + "=" * 60)
    print("RELATÓRIO DE PERSISTÊNCIA - PARQUET LOCAL (data/silver/)")
    print("=" * 60)

    tables = ["bacen_sgs", "b3_cotacoes", "cvm_demonstrativos"]
    for t in tables:
        path_parquet = SILVER_DIR / f"{t}.parquet"
        dir_partition = SILVER_DIR / t

        if path_parquet.exists():
            df = pd.read_parquet(path_parquet)
            size_kb = path_parquet.stat().st_size / 1024
            print(f"- Tabela '{t}': {len(df):,} linhas | Tamanho: {size_kb:.1f} KB (arquivo único)")
        elif dir_partition.exists() and dir_partition.is_dir():
            files = list(dir_partition.rglob("*.parquet"))
            total_rows = 0
            total_size = sum(f.stat().st_size for f in files) / 1024
            for f in files:
                df = pd.read_parquet(f)
                total_rows += len(df)
            print(f"- Tabela '{t}': {total_rows:,} linhas | {len(files)} partições | Tamanho Total: {total_size:.1f} KB")
        else:
            print(f"- Tabela '{t}': NÃO ENCONTRADA em {SILVER_DIR}")

    print("\nExecução concluída.")


if __name__ == "__main__":
    main()