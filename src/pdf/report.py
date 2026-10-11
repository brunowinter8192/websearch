# INFRASTRUCTURE
from dataclasses import dataclass


# FUNCTIONS
@dataclass(frozen=True)
class Report:
    text: str
    ok: bool


class WorkflowError(Exception):
    def __init__(self, failure_class: str, message: str):
        super().__init__(message)
        self.failure_class = failure_class
