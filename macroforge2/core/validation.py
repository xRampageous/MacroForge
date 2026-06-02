"""Preflight validation hooks for MacroForge 2.0."""

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    message: str
    action_index: int | None = None


def validate_actions(actions: Iterable[object]) -> List[ValidationIssue]:
    """Return non-fatal validation issues for a macro action list.

    This starts lightweight so it can be introduced safely. Future patches should
    add key-map validation, jump-target validation, image-path checks, and loop
    sanity checks here before playback begins.
    """
    issues: List[ValidationIssue] = []
    for idx, action in enumerate(actions):
        action_type = getattr(action, "action_type", None)
        if not action_type:
            issues.append(ValidationIssue("warning", "Action is missing an action_type", idx))
        if getattr(action, "repeat_count", 1) is None:
            issues.append(ValidationIssue("warning", "Action repeat_count is missing", idx))
    return issues
