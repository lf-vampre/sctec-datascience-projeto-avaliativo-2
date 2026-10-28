"""Script de execução e validação completa da camada Ouro em modo Produção."""

import sys
from pathlib import Path

# Adiciona a raiz do projeto ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings, universe
from src.etl.warehouse.persistence import Persistence
from src.etl.warehouse.star_schema import StarSchemaBuilder
from src.models.contracts import PipelineParams


def main() -> None:
    """Executa a construção das dimensões e fatos da camada Ouro no ambiente de Produção."""
    # Em main(), substituir a instanciação de PipelineParams por:

    bacen_start = getattr(settings, "DEFAULT_BACEN_START_DATE", "2021-01-01")
    bacen_end = getattr(settings, "DEFAULT_BACEN_END_DATE", "2023-12-31")
    b3_start = getattr(settings, "DEFAULT_B3_START_DATE", "2021-01-01")
    b3_end = getattr(settings, "DEFAULT_B3_END_DATE", "2023-12-31")
    cvm_anos = getattr(settings, "DEFAULT_CVM_ANOS", getattr(settings, "DEFAULT_CVM_YEARS", [2021, 2022, 2023]))

    params = PipelineParams(
        tickers=list(universe.COMPANIES.keys()),
        bacen_periodo=(bacen_start, bacen_end),
        b3_periodo=(b3_start, b3_end),
        cvm_anos=cvm_anos,
        is_sandbox=False,
    )

    persistence = Persistence()
    builder = StarSchemaBuilder(persistence=persistence)

    print("=== Executando Camada Ouro (Modo Produção) ===")

    print("\n1. Construindo Dimensões...")
    res_dims = builder.run_dims(params)
    print(f"Dimensões concluídas: OK={res_dims.ok}, Linhas={res_dims.rows}, Tempo={res_dims.duration_s:.2f}s")
    if res_dims.error:
        print(f"Erro: {res_dims.error}")

    for source in ["bacen", "b3", "cvm"]:
        print(f"\n2. Populando Fato ({source.upper()})...")
        res_gold = builder.run_gold(source, params)
        print(f"Fato {source} concluído: OK={res_gold.ok}, Linhas={res_gold.rows}, Tempo={res_gold.duration_s:.2f}s")
        if res_gold.warnings:
            print(f"Warnings: {res_gold.warnings}")
        if res_gold.error:
            print(f"Erro: {res_gold.error}")

    print("\n=== Relatório de Saúde (Health Report) ===")
    report = persistence.health_report(modo="producao")
    for tabela, stats in report.items():
        print(
            f"- {tabela}: Parquet={stats['linhas_parquet']} | Neon={stats['linhas_neon']} | "
            f"Manifest={stats['linhas_manifest']} | Fonte={stats['fonte_ativa']} | "
            f"Divergência={stats['divergencia']}"
        )


if __name__ == "__main__":
    main()