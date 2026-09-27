"""Erros do Job Manager."""


class JobManagerError(Exception):
    """Erro base."""


class JobNotFound(JobManagerError):
    pass


class InvalidTransition(JobManagerError):
    pass


class ProjectBusy(JobManagerError):
    """Já existe job PLANNING/RUNNING/STOPPING no mesmo projeto (D-0036)."""


class JobAlreadyClaimed(JobManagerError):
    """Outra tentativa viva detém o lease do job."""


class NothingToRun(JobManagerError):
    pass


class LeaseLost(JobManagerError):
    """Fencing: a tentativa não é mais a dona do job (15 §5). O executor deve parar sem escrever."""


class FactoryStopped(JobManagerError):
    """STOP da fábrica ativo (08 §9): nenhum despacho."""


class ValidationRequired(JobManagerError):
    """COMPLETED exige validação aprovada da tentativa atual."""


class UnknownJobType(JobManagerError):
    pass


class StepError(JobManagerError):
    """Falha de passo recuperável (conta como tentativa falha)."""


class FatalStepError(JobManagerError):
    """Falha não recuperável: o job vai para FAILED."""
