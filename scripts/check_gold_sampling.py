"""Script de conferência por amostragem de indicadores da Ouro contra fontes oficiais."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.etl.warehouse.persistence import Persistence


def main() -> None:
    persistence = Persistence()

    print("=== Conferência por Amostragem (Ouro vs Fonte Externa) ===")

    df_macro = persistence.load("gold", "fato_macro", modo="producao")
    df_ind = persistence.load("gold", "dim_indicador", modo="producao")
    df_dem = persistence.load("gold", "fato_demonstrativos", modo="producao")
    df_emp = persistence.load("gold", "dim_empresa", modo="producao")

    # 1. BACEN: Selic Meta (busca a data exata ou mais próxima)
    sk_ind_selic = int(df_ind[df_ind["codigo"] == "SELIC_META"]["sk_indicador"].values[0])
    selic_df = df_macro[df_macro["sk_indicador"] == sk_ind_selic].sort_values("sk_tempo")
    
    # Amostra em dez/2023
    selic_sample = selic_df[selic_df["sk_tempo"] <= 20231228].tail(1)
    val_selic_ouro = float(selic_sample["valor"].values[0]) if not selic_sample.empty else None
    dt_selic = selic_sample["sk_tempo"].values[0] if not selic_sample.empty else None

    print(f"\n1. SELIC_META (Data Ouro: {dt_selic}):")
    print(f"   - Ouro: {val_selic_ouro}% a.a.")
    print(f"   - Fonte Externa BACEN: 11.75% a.a.")
    print(f"   - Status: {'BATIDO (100%)' if val_selic_ouro == 11.75 else 'DIVERGENTE'}")

    # 2. BACEN: IPCA 12M
    sk_ind_ipca = int(df_ind[df_ind["codigo"] == "IPCA_12M"]["sk_indicador"].values[0])
    ipca_df = df_macro[df_macro["sk_indicador"] == sk_ind_ipca].sort_values("sk_tempo")
    
    ipca_sample = ipca_df[ipca_df["sk_tempo"] <= 20231231].tail(1)
    val_ipca_ouro = float(ipca_sample["valor"].values[0]) if not ipca_sample.empty else None
    dt_ipca = ipca_sample["sk_tempo"].values[0] if not ipca_sample.empty else None

    print(f"\n2. IPCA_12M (Data Ouro: {dt_ipca}):")
    print(f"   - Ouro: {val_ipca_ouro}% a.a.")
    print(f"   - Fonte Externa BACEN: 4.62% a.a.")
    print(f"   - Status: {'BATIDO (100%)' if val_ipca_ouro == 4.62 else 'DIVERGENTE'}")

    # 3. CVM: WEGE3 Exercício 2023
    sk_emp_wege = int(df_emp[df_emp["ticker"] == "WEGE3"]["sk_empresa"].values[0])
    sk_tempo_2023 = 20231231
    sk_ind_rl = int(df_ind[df_ind["codigo"] == "RECEITA_LIQUIDA"]["sk_indicador"].values[0])
    sk_ind_ll = int(df_ind[df_ind["codigo"] == "LUCRO_LIQUIDO"]["sk_indicador"].values[0])

    rl_wege = df_dem[
        (df_dem["sk_empresa"] == sk_emp_wege)
        & (df_dem["sk_tempo"] == sk_tempo_2023)
        & (df_dem["sk_indicador"] == sk_ind_rl)
    ]["valor"].values

    ll_wege = df_dem[
        (df_dem["sk_empresa"] == sk_emp_wege)
        & (df_dem["sk_tempo"] == sk_tempo_2023)
        & (df_dem["sk_indicador"] == sk_ind_ll)
    ]["valor"].values

    val_rl_wege = float(rl_wege[0]) if len(rl_wege) > 0 else None
    val_ll_wege = float(ll_wege[0]) if len(ll_wege) > 0 else None

    print(f"\n3. WEGE3 DFP 2023:")
    print(f"   - Receita Líquida Ouro: R$ {val_rl_wege:,.2f}" if val_rl_wege else "   - Receita Líquida Ouro: N/A")
    print(f"   - Receita Líquida DFP:  R$ 32,840,981,000.00")
    print(f"   - Lucro Líquido Ouro:   R$ {val_ll_wege:,.2f}" if val_ll_wege else "   - Lucro Líquido Ouro: N/A")
    print(f"   - Lucro Líquido DFP:    R$ 5,732,036,000.00")


if __name__ == "__main__":
    main()