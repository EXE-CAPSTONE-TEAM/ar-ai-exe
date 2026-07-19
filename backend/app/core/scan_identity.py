from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControlPlaneScanPrincipal:
    """Canonical identity and capability embedded in a project-scoped scan JWT."""

    user_id: str
    project_id: str
    completion_token: str
    project_name: str
    web_project_url: str
