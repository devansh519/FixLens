from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering


_VERSION_PATTERN = re.compile(
    r"^[vV]?"
    r"(?P<major>0|[1-9]\d*)"
    r"\."
    r"(?P<minor>0|[1-9]\d*)"
    r"\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:[-+].*)?$"
)


@total_ordering
@dataclass(frozen=True)
class SemanticVersion:
    """Minimal semantic-version representation."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, version: str) -> "SemanticVersion":
        """Parse a semantic version such as v2.5.1."""
        if not isinstance(version, str):
            raise TypeError("Version must be a string.")

        match = _VERSION_PATTERN.match(version.strip())

        if not match:
            raise ValueError(
                f"Unsupported semantic version: {version!r}"
            )

        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented

        return (
            self.major,
            self.minor,
            self.patch,
        ) == (
            other.major,
            other.minor,
            other.patch,
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented

        return (
            self.major,
            self.minor,
            self.patch,
        ) < (
            other.major,
            other.minor,
            other.patch,
        )


class VersionVerifier:
    """Perform deterministic version comparisons."""

    @staticmethod
    def parse(version: str) -> SemanticVersion:
        return SemanticVersion.parse(version)

    @staticmethod
    def is_at_least(
        actual_version: str,
        required_version: str,
    ) -> bool:
        """Return whether actual_version >= required_version."""
        actual = SemanticVersion.parse(actual_version)
        required = SemanticVersion.parse(required_version)

        return actual >= required

    @staticmethod
    def is_between(
        version: str,
        minimum_version: str,
        maximum_version: str,
    ) -> bool:
        """Return whether minimum_version <= version <= maximum_version."""
        current = SemanticVersion.parse(version)
        minimum = SemanticVersion.parse(minimum_version)
        maximum = SemanticVersion.parse(maximum_version)

        if minimum > maximum:
            raise ValueError(
                "minimum_version cannot be greater than maximum_version."
            )

        return minimum <= current <= maximum

    @staticmethod
    def compare(
        first_version: str,
        second_version: str,
    ) -> int:
        """
        Compare two versions.

        Returns:
            -1 if first_version is lower
             0 if both versions are equal
             1 if first_version is higher
        """
        first = SemanticVersion.parse(first_version)
        second = SemanticVersion.parse(second_version)

        if first < second:
            return -1

        if first > second:
            return 1

        return 0