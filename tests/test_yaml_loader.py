from pathlib import Path

import pytest

from pytest_agent_eval.yaml_loader import load_transcript

SAMPLE = Path(__file__).parent / "fixtures" / "sample_transcript.yaml"


def test_load_transcript_parses_fields():
    t = load_transcript(SAMPLE)
    assert t.id == "sample_booking"
    assert t.threshold == 1.0
    assert t.runs == 1
    assert t.tags == ["gate:booking"]
    assert len(t.turns) == 1
    assert t.turns[0].user == "Book me a slot"
    assert t.turns[0].expect.reply_contains_any == ["confirmed", "booked"]
    assert t.turns[0].expect.tool_calls_include == ["book_slot"]


def test_yaml_discovery_and_collection(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{"tests/evals/hello": ("id: hello_test\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n")},
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "confirmed", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live", "--collect-only", "-q")
    result.stdout.fnmatch_lines(["*hello_test*"])


def test_yaml_item_passes_with_matching_agent(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{
            "tests/evals/booking": (
                "id: booking_ok\n"
                "threshold: 1.0\n"
                "runs: 1\n"
                "turns:\n"
                "  - user: book me\n"
                "    expect:\n"
                "      reply_contains_any:\n"
                "        - confirmed\n"
            )
        },
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "booking confirmed!", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*booking_ok*PASSED*"])
    assert result.ret == 0


def test_yaml_item_fails_with_non_matching_agent(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{
            "tests/evals/fail_test": (
                "id: fail_case\n"
                "threshold: 1.0\n"
                "runs: 1\n"
                "turns:\n"
                "  - user: book me\n"
                "    expect:\n"
                "      reply_contains_any:\n"
                "        - confirmed\n"
            )
        },
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "error", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*fail_case*FAILED*"])
    assert result.ret != 0
