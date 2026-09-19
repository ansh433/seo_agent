"""Thin HTTP transport for technical audit requests."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from seo_agent.audit.models import AuditRequest, AuditResponse
from seo_agent.audit.service import AuditService

router = APIRouter(prefix="/audits", tags=["audits"])


def require_audit_service(request: Request) -> AuditService:
    """Require the lifespan-initialized audit capability."""
    service = getattr(request.app.state, "audit_service", None)
    if not isinstance(service, AuditService):
        raise RuntimeError("Audit service is not initialized")
    return service


@router.post(
    "",
    response_model=AuditResponse,
    status_code=status.HTTP_200_OK,
)
async def create_audit(
    audit_request: AuditRequest,
    service: Annotated[AuditService, Depends(require_audit_service)],
) -> AuditResponse:
    """Run a bounded audit for one public website."""
    report = await service.audit_website(audit_request.website_url)
    return AuditResponse(report=report)
