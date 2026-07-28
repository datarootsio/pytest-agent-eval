"""Declarative builder for the inner pytest projects the plugin is tested against.

Seventeen tests hand-rolled the same ``makeini`` call and nine repeated the same
``llm_eval_agent`` conftest stub. Both now come from here, so the shape of an inner
project is stated once and each test says only what makes it different.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import pytest

# Inner runs get their own ini and so cannot see the outer asyncio settings.
_DEFAULT_INI = "asyncio_mode = auto\n"


def static_agent(reply: str = "ok", tool_calls: Sequence[str] = ()) -> str:
    """Conftest source for an ``llm_eval_agent`` returning a fixed reply and tool calls."""
    return f"""
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return {reply!r}, {list(tool_calls)!r}
            return agent
        """


def keyword_agent(replies: Mapping[str, str], default: str = "sorry") -> str:
    """Conftest source for an agent whose reply depends on a keyword in the user message."""
    return f"""
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                message = history[-1]["content"].lower()
                for keyword, reply in {dict(replies)!r}.items():
                    if keyword in message:
                        return reply, []
                return {default!r}, []
            return agent
        """


def raising_agent(message: str) -> str:
    """Conftest source for an agent that raises, to exercise non-assertion failure paths."""
    return f"""
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                raise RuntimeError({message!r})
            return agent
        """


@dataclass(frozen=True)
class EvalProject:
    """One inner pytest project: ini, pyproject, conftest and YAML transcripts.

    Args:
        conftest: Conftest source, usually from :func:`static_agent`. Omitted entirely
            when empty, which is how the missing-fixture path is exercised.
        pyproject: ``pyproject.toml`` body, for ``[tool.agent_eval]`` settings.
        transcripts: Mapping of path stem (e.g. ``"tests/evals/booking"``) to YAML text.
        files: Extra Python modules, passed through to ``makepyfile``.
        ini: Body of the ``[pytest]`` section.
    """

    conftest: str = ""
    pyproject: str = ""
    transcripts: Mapping[str, str] = field(default_factory=dict)
    files: Mapping[str, str] = field(default_factory=dict)
    ini: str = _DEFAULT_INI

    def write(self, pytester: pytest.Pytester) -> None:
        """Materialise the project into the pytester temp directory."""
        # pyproject first, then ini: pytest reads config from tox.ini here, and this is
        # the order the hand-rolled versions used.
        if self.pyproject:
            pytester.makepyprojecttoml(self.pyproject)
        pytester.makeini(f"[pytest]\n{self.ini}")
        if self.conftest:
            pytester.makeconftest(self.conftest)
        if self.transcripts:
            pytester.makefile(".yaml", **dict(self.transcripts))
        if self.files:
            pytester.makepyfile(**dict(self.files))
