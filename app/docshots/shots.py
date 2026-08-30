"""Declarative registry of documentation screenshots."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ShotSpec:
    name: str
    qml_type: str
    workspace_name: str = ""
    selected_host: str = ""


_SHOTS = {
    "welcome": ShotSpec("welcome", "Welcome"),
    "workspace": ShotSpec(
        "workspace",
        "Main",
        workspace_name="Campus Network Lab",
    ),
    "devices": ShotSpec(
        "devices",
        "Main",
        workspace_name="Campus Network Lab",
        selected_host="192.0.2.1",
    ),
}

SHOT_REGISTRY: Mapping[str, ShotSpec] = MappingProxyType(_SHOTS)

VLAN_WORKFLOW_FILENAMES = (
    "01-select-switch.png",
    "02-open-vlan.png",
    "03-add-vlan.png",
    "04-vlan-id.png",
    "05-vlan-name.png",
    "06-vlan-state.png",
    "07-ready-to-save.png",
    "08-vlan-created.png",
    "09-view-preview.png",
)

DIALOG_REGRESSION_FILENAMES = (
    "view-push-dialog.png",
    "snapshot-history-dialog.png",
    "create-project-dialog.png",
    "create-project-password-dialog.png",
)


def resolve_shots(name: str) -> tuple[ShotSpec, ...]:
    if name == "all":
        return tuple(SHOT_REGISTRY.values())
    try:
        return (SHOT_REGISTRY[name],)
    except KeyError as exc:
        known = ", ".join((*SHOT_REGISTRY, "all"))
        raise ValueError(f"Unknown shot {name!r}. Choose one of: {known}.") from exc


__all__ = [
    "SHOT_REGISTRY",
    "DIALOG_REGRESSION_FILENAMES",
    "VLAN_WORKFLOW_FILENAMES",
    "ShotSpec",
    "resolve_shots",
]
