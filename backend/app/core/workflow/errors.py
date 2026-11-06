from __future__ import annotations


class WorkflowError(Exception):
    """Base class for workflow failures."""


class WorkflowValidationError(WorkflowError):
    """Raised when a workflow definition is invalid."""


class NodeExecutionError(WorkflowError):
    """Raised when a node exhausts its retry budget."""

    def __init__(
        self,
        node_id: str,
        node_type: str,
        attempts: int,
        cause: BaseException | None,
    ) -> None:
        self.node_id = node_id
        self.node_type = node_type
        self.attempts = attempts
        self.cause = cause
        detail = f"{type(cause).__name__}: {cause}" if cause is not None else "unknown error"
        super().__init__(
            f"node {node_id} ({node_type}) failed after {attempts} attempt(s): {detail}"
        )
