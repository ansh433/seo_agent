"""Application service for running one bounded website audit."""

from seo_agent.audit.errors import AuditError
from seo_agent.audit.models import AuditLimits, AuditReport
from seo_agent.audit.workflow import AuditGraph, initial_audit_state


class AuditDidNotCompleteError(AuditError):
    """Raised when the graph terminates without its required report."""


class AuditService:
    """Invoke the compiled workflow with isolated request state."""

    def __init__(self, graph: AuditGraph, limits: AuditLimits) -> None:
        self._graph = graph
        self._limits = limits

    async def audit_website(self, website_url: str) -> AuditReport:
        """Run one audit and return its validated final report."""
        result = await self._graph.ainvoke(initial_audit_state(website_url, self._limits))
        report = result.get("report")
        if report is None:
            raise AuditDidNotCompleteError("The audit workflow did not produce a report")
        return report
