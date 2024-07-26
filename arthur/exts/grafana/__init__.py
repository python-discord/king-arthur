from dataclasses import dataclass


@dataclass(frozen=True)
class MissingMembers:
    """Number of members that were missing from the Grafana team, and how many could be added."""

    count: int
    successfully_added: int


@dataclass(frozen=True)
class SyncFigures:
    """Figures related to a single sync members task run."""

    added: MissingMembers
    removed: int
