"""The Message contract.

Message replaced a plain dict in the history handed to user-written agents and
evaluators, so every dict behaviour those callers could have relied on is pinned here.
"""

from __future__ import annotations

import json

import pytest

from pytest_agent_eval.models import Message


def test_our_code_reads_attributes():
    msg = Message(role="user", content="hi")
    assert msg.role == "user"
    assert msg.content == "hi"
    assert msg.audio is None


def test_callers_can_still_subscript():
    """Every documented agent example does history[-1]["content"]."""
    assert Message(role="user", content="hi")["content"] == "hi"
    assert Message(role="user", content="hi")["role"] == "user"


def test_compares_equal_to_the_dict_it_replaced():
    """eq=False hands equality to Mapping, which is what makes the swap invisible."""
    assert Message(role="user", content="hi") == {"role": "user", "content": "hi"}
    assert Message(role="user", content="hi", audio="a.wav") == {
        "role": "user",
        "content": "hi",
        "audio": "a.wav",
    }
    assert Message(role="user", content="hi") != {"role": "user", "content": "bye"}


def test_unpacks_into_a_dict():
    assert dict(Message(role="assistant", content="ok")) == {"role": "assistant", "content": "ok"}
    assert {**Message(role="assistant", content="ok")} == {"role": "assistant", "content": "ok"}


def test_absent_audio_is_absent_not_none():
    """A None audio must look like a missing key, or text adapters would forward it."""
    msg = Message(role="user", content="hi")
    assert "audio" not in msg
    assert msg.get("audio") is None
    assert list(msg) == ["role", "content"]
    assert len(msg) == 2
    with pytest.raises(KeyError):
        msg["audio"]


def test_present_audio_is_a_real_key():
    msg = Message(role="user", content="hi", audio="turn1.wav")
    assert "audio" in msg
    assert msg["audio"] == "turn1.wav"
    assert list(msg) == ["role", "content", "audio"]
    assert len(msg) == 3


def test_unknown_keys_raise_key_error():
    with pytest.raises(KeyError):
        Message(role="user", content="hi")["nope"]


def test_to_dict_drops_the_plugin_internal_audio_key():
    """The OpenAI API rejects unknown message keys, and the runner sets audio on voice turns."""
    msg = Message(role="user", content="hi", audio="turn1.wav")
    assert msg.to_dict() == {"role": "user", "content": "hi"}
    assert msg.to_dict(include_audio=True) == {"role": "user", "content": "hi", "audio": "turn1.wav"}


def test_is_immutable():
    with pytest.raises(Exception, match="cannot assign|immutable|frozen"):
        Message(role="user", content="hi").content = "changed"  # type: ignore[misc]


def test_direct_json_serialisation_is_refused():
    """Deliberate: it forces every serialisation boundary to say to_dict() out loud."""
    with pytest.raises(TypeError):
        json.dumps(Message(role="user", content="hi"))
    # ...and the sanctioned route works.
    assert json.loads(json.dumps(Message(role="user", content="hi").to_dict())) == {
        "role": "user",
        "content": "hi",
    }


def test_has_no_instance_dict_under_slots():
    assert not hasattr(Message(role="user", content="hi"), "__dict__")
