"""Script de execução e validação da carga Bronze em modo Produção."""

from pathlib import Path
import pandas as pd

from src.config.universe import COMPANIES
from src.etl.extractors.b3_extractor import B3Extractor
from src.etl.extractors.bacen_extractor import BacenExtractor
from src.etl.extractors.cadastro_extractor import CadastroExtractor
from src.etl.extractors.cvm_extractor import CvmExtractor
from src.etl.warehouse.persistence import Persistence
from src.etl.base import PipelineLogger
from src.models.contracts import PipelineParams
from src.utils.paths import BRONZE_DIR


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

    extractors = [
        ("CadastroExtractor", CadastroExtractor(logger=logger, storage_writer=persistence)),
        ("BacenExtractor", BacenExtractor(logger=logger, storage_writer=persistence)),
        ("B3Extractor", B3Extractor(logger=logger, storage_writer=persistence)),
        ("CvmExtractor", CvmExtractor(logger=logger, storage_writer=persistence)),
    ]

    print("=" * 60)
    print("INICIANDO CARGA BRONZE (MODO PRODUÇÃO)")
    print(f"Tickers ({len(tickers)}): {tickers}")
    print("=" * 60)

    results = {}
    for name, extractor in extractors:
        print(f"\n---> Executando {name}...")
        res = extractor.run_bronze(params)
        results[name] = res
        print(f"Status: {'OK' if res.ok else 'FALHA'} | Linhas: {res.rows} | Erro: {res.error or 'Nenhum'}")

    print("\n" + "=" * 60)
    print("RELATÓRIO DE PERSISTÊNCIA - PARQUET LOCAL (data/bronze/)")
    print("=" * 60)

    tables = ["cvm_cadastro", "bacen_sgs", "b3_cotacoes", "cvm_dre", "cvm_bpa", "cvm_bpp"]
    for t in tables:
        file_path = BRONZE_DIR / f"{t}.parquet"
        if file_path.exists():
            df = pd.read_parquet(file_path)
            print(f"- Tabela '{t}': {len(df):,} linhas | Tamanho: {file_path.stat().st_size / 1024:.1f} KB")
        else:
            print(f"- Tabela '{t}': NATIVE PARQUET NÃO ENCONTRADO em {file_path}")

    print("\nExecução concluída.")


if __name__ == "__main__":
    main()