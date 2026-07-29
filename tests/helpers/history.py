"""Builders for the conversation history handed to agents and evaluators."""

from __future__ import annotations

from pytest_agent_eval.models import History, Message


def user(content: str, *, audio: str | None = None) -> Message:
    """One user message, optionally carrying a WAV path for a voice turn."""
    return Message(role="user", content=content, audio=audio)


def assistant(content: str) -> Message:
    """One assistant message."""
    return Message(role="assistant", content=content)


def system(content: str) -> Message:
    """One system message."""
    return Message(role="system", content=content)


def one_turn(content: str = "hi", *, audio: str | None = None) -> History:
    """A history containing just the current user turn — what a first turn looks like."""
    return [user(content, audio=audio)]
