"""Mapeador de contas contábeis CVM para códigos de indicadores padronizados."""

from typing import Dict, List, Optional, Tuple
import pandas as pd

from src.config.accounts import FINANCIAL_ACCOUNTS, INDUSTRIAL_ACCOUNTS
from src.config.universe import COMPANIES
from src.etl.base import PipelineLogger


class AccountMapper:
    """Mapeia contas contábeis de demonstrativos CVM em indicadores padronizados."""

    def __init__(self, logger: Optional[PipelineLogger] = None) -> None:
        self.logger = logger
        # Mapa cd_cvm -> tipo_plano
        self.cvm_to_tipo_plano: Dict[int, str] = {
            info.cd_cvm: info.tipo_plano
            for info in COMPANIES.values()
        }

    def map_accounts(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Aplica o mapeamento de indicador_codigo sobre o DataFrame de demonstrativos CVM."""
        warnings: List[str] = []
        if df.empty:
            return df, warnings

        df_mapped = df.copy()
        df_mapped["codigo_indicador"] = None

        # 1. Mapeamento Plano Industrial (por CD_CONTA, DEMONSTRATIVO e ST_CONTA_FIXA)
        ind_lookup = {
            (spec["cd_conta"], spec["demonstrativo"]): code
            for code, spec in INDUSTRIAL_ACCOUNTS.items()
        }

        # 2. Mapeamento Plano Financeiro (por busca em DS_CONTA e DEMONSTRATIVO)
        fin_lookup = FINANCIAL_ACCOUNTS

        mapped_codes: List[Optional[str]] = []

        for idx in range(len(df_mapped)):
            row = df_mapped.iloc[idx]
            cd_cvm = row.get("cd_cvm")
            tipo_plano = self.cvm_to_tipo_plano.get(cd_cvm, "industrial")
            cd_conta = str(row.get("cd_conta", "")).strip()
            ds_conta = str(row.get("ds_conta", "")).strip().lower()
            demonstrativo = str(row.get("demonstrativo", "")).strip().upper()
            st_conta_fixa = str(row.get("st_conta_fixa", "")).strip().upper()

            code_found: Optional[str] = None

            if tipo_plano == "industrial":
                if st_conta_fixa == "S":
                    code_found = ind_lookup.get((cd_conta, demonstrativo))
            elif tipo_plano == "financeira":
                for ind_code, spec in fin_lookup.items():
                    if spec["demonstrativo"] == demonstrativo:
                        if any(kw in ds_conta for kw in spec["keywords"]):
                            code_found = ind_code
                            break

            mapped_codes.append(code_found)

        df_mapped["codigo_indicador"] = mapped_codes

        # 3. Validações e Alertas de Ambiguidade / Cobertura
        mapped_rows = df_mapped[df_mapped["codigo_indicador"].notna()]

        # Validação de Ambiguidade: mais de um código igual para mesma empresa, exercício e demonstrativo
        group_keys = ["cd_cvm", "ano", "demonstrativo", "codigo_indicador"]
        ambiguous = mapped_rows[mapped_rows.duplicated(subset=group_keys, keep=False)]
        if not ambiguous.empty:
            dup_info = ambiguous[group_keys].drop_duplicates().to_dict(orient="records")
            warn_amb = f"Detectada ambiguidade no mapeamento de contas CVM: {dup_info}"
            warnings.append(warn_amb)
            if self.logger:
                self.logger.emit("WARNING", "AccountMapper", "AMBIGUITY", warn_amb)

        # Validação para industriais: verificar se faltam contas obrigatórias
        for cd_cvm, df_emp in df_mapped.groupby("cd_cvm"):
            tipo_plano = self.cvm_to_tipo_plano.get(cd_cvm, "industrial")
            if tipo_plano == "industrial":
                for ano, df_ano in df_emp.groupby("ano"):
                    found_codes = set(df_ano["codigo_indicador"].dropna().unique())
                    missing_mandatory = set(INDUSTRIAL_ACCOUNTS.keys()) - found_codes
                    if missing_mandatory:
                        warn_miss = f"Empresa CD_CVM {cd_cvm} (Ano {ano}) sem contas mapeadas: {sorted(list(missing_mandatory))}"
                        warnings.append(warn_miss)
                        if self.logger:
                            self.logger.emit("WARNING", "AccountMapper", "MISSING_ACCOUNTS", warn_miss)

        return df_mapped, warnings