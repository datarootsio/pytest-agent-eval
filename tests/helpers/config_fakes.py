"""A typed stand-in for the pytest Config object that load_config() consumes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FakePytestConfig:
    """Minimal pytest.Config for config loading.

    A typed fake rather than a MagicMock: load_config reads ``rootpath`` (a real Path)
    and calls ``getoption``, and a MagicMock silently satisfies either with another mock
    — which is how a rootdir/rootpath mix-up survives a green test run.

    Args:
        rootpath: Directory searched for pyproject.toml.
        options: Values ``getoption`` should return, by option name.
        unknown_option_error: Raised for any option not in ``options``, mimicking a
            pytest run where the plugin's options were never registered.
    """

    rootpath: Path
    options: dict[str, Any] = field(default_factory=dict)
    unknown_option_error: BaseException | None = None

    def getoption(self, name: str, default: Any = None) -> Any:
        """Return a configured option value, or raise as an unregistered option would."""
        if name in self.options:
            return self.options[name]
        if self.unknown_option_error is not None:
            raise self.unknown_option_error
        return default
