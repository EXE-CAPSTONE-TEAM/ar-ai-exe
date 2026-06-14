from fastapi import APIRouter

from app.schemas.system import EditorReadinessResponse, ReconstructionReadinessResponse
from app.services.editor_readiness import EditorReadinessService
from app.services.reconstruction_toolchain import ReconstructionToolchainService


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/reconstruction-readiness", response_model=ReconstructionReadinessResponse)
def reconstruction_readiness() -> ReconstructionReadinessResponse:
    readiness = ReconstructionToolchainService().check()
    return ReconstructionReadinessResponse.model_validate(readiness.to_dict())


@router.get("/editor-readiness", response_model=EditorReadinessResponse)
def editor_readiness() -> EditorReadinessResponse:
    return EditorReadinessResponse.model_validate(EditorReadinessService().check())
