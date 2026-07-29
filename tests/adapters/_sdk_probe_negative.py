"""Type-level probe with the polarity inverted: this module MUST NOT type-check.

``test_sdk_types.py`` runs ``ty`` over it and asserts it fails, for exactly the two
reasons below. Separate from ``_sdk_probe.py``, which must stay green — mixing them would
make a real regression indistinguishable from the expected failures. The positive control
is ``_sdk_probe.probe_openai_message_param``, so these cannot be read as an unsatisfiable
annotation.

It answers a recurring review question — why does ``openai._as_param`` dispatch on
``role`` instead of handing the SDK ``asdict(message)``? — with the checker rather than a
comment, because both reasons are static:

* ``asdict`` reflects ``dataclasses.fields()``, so it always emits ``audio``, which
  ``runner.py`` sets on every turn. ``audio`` is not a key on
  ``ChatCompletionUserMessageParam``, and on the assistant param it must be ``{"id": str}``
  rather than a WAV path. ``Message.__iter__`` treats unset ``audio`` as absent; ``asdict``
  bypasses that. Commit 5f22d19 records it as a shipped bug.
* ``messages`` is a union of six per-role TypedDicts. Neither ``dict[str, Any]`` nor
  ``dict[str, str]`` is assignable to a TypedDict, and both erase ``role: Literal[...]``,
  so nothing narrows the union.
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
