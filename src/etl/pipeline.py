"""Orquestrador do pipeline ETL com controle de passos, dependências, modos e travas."""

from dataclasses import asdict, dataclass
import hmac
from typing import Any, Dict, List, Optional, Tuple

from src.config import settings, universe
from src.etl.base import (
    PipelineLogger,
    get_layer_path,
    release_lock,
    seconds_until_allowed,
    try_acquire,
)
from src.models.contracts import PipelineParams, StepResult
from src.utils.memory import release


@dataclass(frozen=True)
class Step:
    """Representa um passo do pipeline ETL."""

    step_id: str
    fonte: str
    camada: str
    rotulo: str
    depende_de: Optional[str] = None


def autorizar(senha_digitada: Optional[str], senha_esperada: Optional[str]) -> str:
    """Decide o modo de execução baseado na verificação em tempo constante da senha."""
    if not senha_esperada or not senha_digitada:
        return "sandbox"

    if hmac.compare_digest(senha_digitada.encode("utf-8"), senha_esperada.encode("utf-8")):
        return "producao"

    return "sandbox"


class PipelineOrchestrator:
    """Orquestrador responsável pela execução sequencial controlada dos passos do ETL."""

    def __init__(self, params: PipelineParams, logger: Optional[PipelineLogger] = None):
        self.params = params
        self.logger = logger or PipelineLogger()
        self._resultados: Dict[str, StepResult] = {}

    @property
    def resultados(self) -> Dict[str, StepResult]:
        return self._resultados

    def steps(self) -> List[Step]:
        """Devolve a lista ordenada de passos do pipeline."""
        return [
            Step("cadastro.bronze", "cadastro", "bronze", "Cadastro CVM Bronze"),
            Step("cadastro.silver", "cadastro", "silver", "Cadastro CVM Silver", depende_de="cadastro.bronze"),
            Step("dims", "warehouse", "gold", "Dimensões Star Schema", depende_de="cadastro.silver"),
            Step("bacen.bronze", "bacen", "bronze", "BACEN SGS Bronze"),
            Step("bacen.silver", "bacen", "silver", "BACEN SGS Silver", depende_de="bacen.bronze"),
            Step("bacen.gold", "bacen", "gold", "BACEN SGS Gold", depende_de="bacen.silver"),
            Step("b3.bronze", "b3", "bronze", "B3 Cotações Bronze"),
            Step("b3.silver", "b3", "silver", "B3 Cotações Silver", depende_de="b3.bronze"),
            Step("b3.gold", "b3", "gold", "B3 Cotações Gold", depende_de="b3.silver"),
            Step("cvm.bronze", "cvm", "bronze", "CVM DFPs Bronze"),
            Step("cvm.silver", "cvm", "silver", "CVM DFPs Silver", depende_de="cvm.bronze"),
            Step("cvm.gold", "cvm", "gold", "CVM DFPs Gold", depende_de="cvm.silver"),
        ]

    def validar_params(self, params: PipelineParams) -> None:
        """Valida parâmetros do pipeline respeitando regras de sandbox e universo."""
        if params.bacen_periodo[0] >= params.bacen_periodo[1]:
            raise ValueError("Data inicial do período BACEN deve ser anterior à data final.")

        if params.b3_periodo[0] >= params.b3_periodo[1]:
            raise ValueError("Data inicial do período B3 deve ser anterior à data final.")

        tickers_invalidos = [t for t in params.tickers if t not in universe.COMPANIES]
        if tickers_invalidos:
            raise ValueError(f"Tickers não pertencentes ao universo: {tickers_invalidos}")

        if params.modo == "sandbox":
            teto = getattr(settings, "SANDBOX_MAX_TICKERS", 3)
            if len(params.tickers) > teto:
                raise ValueError(
                    f"Modo sandbox aceita no máximo {teto} tickers. "
                    f"Foram fornecidos {len(params.tickers)}."
                )

    def pode_executar(self, step_id: str) -> Tuple[bool, str]:
        """Verifica se um passo possui pré-requisitos satisfeitos."""
        passos = {s.step_id: s for s in self.steps()}
        if step_id not in passos:
            return False, f"Passo '{step_id}' não existe."

        step = passos[step_id]
        if not step.depende_de:
            return True, "Pronto para execução."

        dep_id = step.depende_de
        if dep_id in self._resultados and self._resultados[dep_id].ok:
            return True, "Pré-requisito concluído na sessão."

        dep_step = passos.get(dep_id)
        if dep_step:
            caminho_dep = get_layer_path(self.params, dep_step.camada)
            if caminho_dep.exists() and any(caminho_dep.iterdir()):
                return True, "Pré-requisito encontrado no destino."

        return False, f"Rode antes: passo pré-requisito '{dep_id}' não foi concluído."

    def _executar_passo_interno(self, step_id: str) -> StepResult:
        """Mapeia e executa a função correspondente com import tardio."""
        if step_id == "cadastro.bronze":
            from src.etl.extractors.cadastro_extractor import CadastroExtractor
            return CadastroExtractor(self.logger).run_bronze(self.params)

        if step_id == "cadastro.silver":
            from src.etl.cleaners.cadastro_cleaner import CadastroCleaner
            return CadastroCleaner(self.logger).run_silver(self.params)

        if step_id == "dims":
            from src.etl.warehouse.star_schema import StarSchemaBuilder
            return StarSchemaBuilder(self.logger).run_dims(self.params)

        if step_id == "bacen.bronze":
            from src.etl.extractors.bacen_extractor import BacenExtractor
            return BacenExtractor(self.logger).run_bronze(self.params)

        if step_id == "bacen.silver":
            from src.etl.cleaners.bacen_cleaner import BacenCleaner
            return BacenCleaner(self.logger).run_silver(self.params)

        if step_id == "bacen.gold":
            from src.etl.warehouse.star_schema import StarSchemaBuilder
            return StarSchemaBuilder(self.logger).run_gold("bacen", self.params)

        if step_id == "b3.bronze":
            from src.etl.extractors.b3_extractor import B3Extractor
            return B3Extractor(self.logger).run_bronze(self.params)

        if step_id == "b3.silver":
            from src.etl.cleaners.b3_cleaner import B3Cleaner
            return B3Cleaner(self.logger).run_silver(self.params)

        if step_id == "b3.gold":
            from src.etl.warehouse.star_schema import StarSchemaBuilder
            return StarSchemaBuilder(self.logger).run_gold("b3", self.params)

        if step_id == "cvm.bronze":
            from src.etl.extractors.cvm_extractor import CVMExtractor
            return CVMExtractor(self.logger).run_bronze(self.params)

        if step_id == "cvm.silver":
            from src.etl.cleaners.cvm_cleaner import CVMCleaner
            return CVMCleaner(self.logger).run_silver(self.params)

        if step_id == "cvm.gold":
            from src.etl.warehouse.star_schema import StarSchemaBuilder
            return StarSchemaBuilder(self.logger).run_gold("cvm", self.params)

        raise ValueError(f"Passo desconhecido: {step_id}")

    def run_step(self, step_id: str) -> StepResult:
        """Executa um passo do pipeline garantindo trava, validações e liberação de memória."""
        pode, msg = self.pode_executar(step_id)
        if not pode:
            res = StepResult(step_id=step_id, ok=False, error=msg)
            self._resultados[step_id] = res
            return res

        try:
            self.validar_params(self.params)
        except Exception as e:
            res = StepResult(step_id=step_id, ok=False, error=str(e))
            self._resultados[step_id] = res
            return res

        restante = seconds_until_allowed(self.params.modo)
        if restante > 0.0:
            res = StepResult(
                step_id=step_id,
                ok=False,
                error=f"Aguarde {restante:.1f}s para próxima execução no modo sandbox.",
            )
            self._resultados[step_id] = res
            return res

        if not try_acquire(self.params.modo):
            res = StepResult(
                step_id=step_id,
                ok=False,
                error=f"Pipeline em execução em outro processo (modo {self.params.modo}).",
            )
            self._resultados[step_id] = res
            return res

        try:
            resultado = self._executar_passo_interno(step_id)
            self._resultados[step_id] = resultado
            return resultado
        except Exception as e:
            resultado = StepResult(step_id=step_id, ok=False, error=str(e))
            self._resultados[step_id] = resultado
            return resultado
        finally:
            release_lock()
            release()

    def estado(self) -> Dict[str, Dict[str, Any]]:
        """Devolve o estado dos resultados em dicionário serializável."""
        return {step_id: asdict(res) for step_id, res in self._resultados.items()}

    def proximo_passo(self) -> Optional[str]:
        """Retorna a identificação do próximo passo pendente e executável."""
        for step in self.steps():
            s_id = step.step_id
            if s_id not in self._resultados or not self._resultados[s_id].ok:
                pode, _ = self.pode_executar(s_id)
                if pode:
                    return s_id
        return None