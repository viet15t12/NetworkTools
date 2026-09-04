from __future__ import annotations

from typing import Any


def normalize_switch_role(role: Any) -> str:
    value = str(role or "").strip().lower()
    return value if value in {"sw2", "sw3"} else ""


def navigation_for_role(role: Any) -> list[dict[str, Any]]:
    """Return only switch surfaces backed by working persistence or reused views."""
    normalized = normalize_switch_role(role)
    if not normalized:
        return []

    features = [
        {"id": "interfaces", "label": "Interfaces", "subfeatures": ["switchPorts"]},
        {
            "id": "switching",
            "label": "Switching",
            "subfeatures": ["vlan", "etherChannel", "stp", "vtp"],
        },
        {
            "id": "security",
            "label": "Security",
            "subfeatures": ["l2Security", "portSecurity"],
        },
        {
            "id": "monitoring",
            "label": "Monitoring",
            "subfeatures": ["portCounters", "macTable"],
        },
    ]
    if normalized == "sw3":
        features[0]["subfeatures"].extend(["routedPorts", "svi"])
        features.insert(
            2,
            {
                "id": "services",
                "label": "Services",
                "subfeatures": ["dhcpServer", "dhcpRelay"],
            },
        )
        for item in features:
            if item["id"] == "security":
                item["subfeatures"].append("acl")
                break
    return features
