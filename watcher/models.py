"""Estruturas de dados compartilhadas."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Publication:
    """Um item publicado detectado por uma fonte.

    item_key deve ser ESTÁVEL e única dentro de (source, target):
    protocolo CVM, nome de arquivo, URL do item, id de resource etc.
    Nunca derive de layout da página.
    """

    item_key: str
    title: str
    url: str
    target: str = ""          # sub-alvo da fonte (ex.: "graos", "passenger", empresa CVM)
    date_text: str = ""       # data de publicação, texto livre p/ exibição
    preview: str = ""         # trecho/resumo para o corpo da mensagem


# Resultados possíveis de uma checagem (gravados em check_runs)
OUTCOME_RAN_NEW = "ran_new"                  # rodou e encontrou novidade
OUTCOME_RAN_NOTHING = "ran_nothing"          # rodou, nada novo
OUTCOME_SKIPPED_WINDOW = "skipped_window"    # fora da janela de dias
OUTCOME_SKIPPED_THROTTLE = "skipped_throttle"  # intervalo mínimo não decorrido
OUTCOME_SKIPPED_DONE = "skipped_done"        # já saiu no período corrente
OUTCOME_DISABLED = "disabled"                # fonte desativada
OUTCOME_ERROR = "error"                      # falha (site fora, layout mudou…)

SKIP_OUTCOMES = {
    OUTCOME_SKIPPED_WINDOW,
    OUTCOME_SKIPPED_THROTTLE,
    OUTCOME_SKIPPED_DONE,
    OUTCOME_DISABLED,
}

# Tipos de disparo
TRIGGER_SCHEDULED = "scheduled"   # Task Scheduler
TRIGGER_FORCED = "forced"         # --force na linha de comando
TRIGGER_MANUAL = "manual"         # botão do painel
TRIGGER_DRYRUN = "dry-run"        # --dry-run (não altera estado nem envia)


@dataclass
class CheckResult:
    source: str
    outcome: str
    detail: str = ""
    duration_ms: int = 0
    new_items: int = 0
    publications: list[Publication] = field(default_factory=list)
