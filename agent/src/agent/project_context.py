from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from agent.src.agent.shared import AGENT_ROOT


@dataclass(frozen=True)
class ProjectContext:
    project_id: str
    spec_dir: str | None
    web_dir: str | None
    api_dir: str | None
    html_files: list[str]
    css_files: list[str]
    js_files: list[str]


def _dirs_by_name(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    return {path.name: path for path in root.iterdir() if path.is_dir()}


def discover_projects() -> list[ProjectContext]:
    spec_dirs = _dirs_by_name(Path(AGENT_ROOT) / "spec")
    web_dirs = _dirs_by_name(Path(AGENT_ROOT) / "web")
    project_ids = sorted(set(spec_dirs) | set(web_dirs))

    results: list[ProjectContext] = []
    for project_id in project_ids:
        spec_dir = spec_dirs.get(project_id)
        web_dir = web_dirs.get(project_id)
        api_dir = web_dir / "api" if web_dir and (web_dir / "api").exists() else None
        results.append(
            ProjectContext(
                project_id=project_id,
                spec_dir=str(spec_dir) if spec_dir else None,
                web_dir=str(web_dir) if web_dir else None,
                api_dir=str(api_dir) if api_dir else None,
                html_files=_sorted_files(web_dir, "*.html"),
                css_files=_sorted_files(web_dir / "css" if web_dir else None, "*.css"),
                js_files=_sorted_files(web_dir / "js" if web_dir else None, "*.js"),
            )
        )
    return results


def _sorted_files(root: Path | None, pattern: str) -> list[str]:
    if root is None or not root.exists():
        return []
    return sorted(str(path) for path in root.glob(pattern) if path.is_file())


def resolve_project_context(project_hint: str | None = None) -> Optional[ProjectContext]:
    projects = discover_projects()
    if not projects:
        return None

    if not project_hint or not project_hint.strip():
        return projects[0] if len(projects) == 1 else None

    hint = project_hint.strip().lower()
    exact = [project for project in projects if project.project_id.lower() == hint]
    if exact:
        return exact[0]

    partial = [project for project in projects if hint in project.project_id.lower()]
    if len(partial) == 1:
        return partial[0]

    return None


def guess_project_id_from_text(text: str) -> str | None:
    text_lower = (text or "").lower()
    for project in discover_projects():
        if project.project_id.lower() in text_lower:
            return project.project_id
    return None


def format_project_context_summary(project: ProjectContext) -> str:
    parts = [
        f"project_id: {project.project_id}",
        f"spec_dir: {project.spec_dir or 'N/A'}",
        f"web_dir: {project.web_dir or 'N/A'}",
        f"api_dir: {project.api_dir or 'N/A'}",
    ]
    if project.html_files:
        parts.append("html_files:\n- " + "\n- ".join(project.html_files))
    if project.css_files:
        parts.append("css_files:\n- " + "\n- ".join(project.css_files))
    if project.js_files:
        parts.append("js_files:\n- " + "\n- ".join(project.js_files))
    return "\n".join(parts)


def list_project_ids() -> list[str]:
    return [project.project_id for project in discover_projects()]


__all__ = [
    "ProjectContext",
    "discover_projects",
    "resolve_project_context",
    "guess_project_id_from_text",
    "format_project_context_summary",
    "list_project_ids",
]
