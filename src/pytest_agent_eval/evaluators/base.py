"""Evaluator protocol and base result type.

Both live in :mod:`pytest_agent_eval.models`, alongside the TurnContext and
EvalResult they reference — Expect.evaluators has to name the protocol, and a
separate module here would make that a circular import. Re-exported so the
documented ``from pytest_agent_eval.evaluators.base import Evaluator`` keeps working.
"""

from __future__ import annotations

from pytest_agent_eval.models import EvalResult, Evaluator, TurnContext

__all__ = ["EvalResult", "Evaluator", "TurnContext"]
