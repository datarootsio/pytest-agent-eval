"""Type-level probe with the polarity inverted: this module MUST NOT type-check.

``test_sdk_types.py`` runs ``ty`` over it and asserts it fails, for exactly the two
reasons below and no others. It is a separate file from ``_sdk_probe.py`` because that
one must stay green — mixing the two would make a real regression indistinguishable from
the expected failures.

What it pins is a review question that keeps coming back: why does
``adapters/openai.py::_as_param`` dispatch on ``role`` instead of just handing the SDK
``dataclasses.asdict(message)`` or ``message.to_dict()``? Both answers are static, so a
runtime test cannot state them:

* ``asdict`` reflects ``dataclasses.fields()``, so it always emits ``audio`` — and
  ``runner.py`` sets ``audio`` on every turn. ``audio`` is not a key on
  ``ChatCompletionUserMessageParam`` at all, and on the assistant param it must be
  ``{"id": str}`` rather than a local WAV path. ``Message.__iter__`` treats an unset
  ``audio`` as an absent key; ``asdict`` bypasses that. Commit 5f22d19 records this as a
  shipped bug.
* ``messages`` is typed as a union of six per-role TypedDicts. Neither ``dict[str, Any]``
  (``asdict``) nor ``dict[str, str]`` (``to_dict``) is assignable to a TypedDict, and both
  erase ``role: Literal[...]``, so nothing narrows the union. The role dispatch is
  load-bearing for the checker, not only for ``audio``.

The positive control lives in ``_sdk_probe.py`` as ``probe_openai_message_param``: it
returns the same annotation from a role literal and passes. Without it, these two failures
could just as well mean the annotation is unsatisfiable.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

    from pytest_agent_eval.models import Message


def asdict_is_not_a_message_param(message: Message) -> ChatCompletionMessageParam:
    """Expected failure 1: ``dict[str, Any]``, and it carries the ``audio`` key."""
    return dataclasses.asdict(message)


def to_dict_is_not_a_message_param(message: Message) -> ChatCompletionMessageParam:
    """Expected failure 2: ``dict[str, str]`` erases ``role``, so the union never narrows."""
    return message.to_dict()
