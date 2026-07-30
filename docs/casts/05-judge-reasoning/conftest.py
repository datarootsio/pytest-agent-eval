import pytest

from pytest_agent_eval import AgentReply

# Turn 2, one reply per run. Two state the new time and repeat BK-1234 unchanged; the
# middle one confirms the change and never says 11am, so the rubric's first requirement
# fails. That is what makes 2/3 the expected score rather than a lucky sample.
RESCHEDULE_REPLIES = (
    "Moved to 11am tomorrow. Your reference is unchanged: BK-1234.",
    "All set, I've updated that booking for you. Reference BK-1234.",
    "Done — 11am instead of 10am tomorrow, still under reference BK-1234.",
)


@pytest.fixture
def booking_agent():
    # An in-process iterator, not a counter file: all three runs happen inside this one
    # pytest process, so there is nothing to survive across processes.
    replies = iter(RESCHEDULE_REPLIES)

    async def agent(history):
        # Turn 1 is the only turn whose history is just the user's opening message.
        if len(history) == 1:
            return AgentReply("Booked for tomorrow at 10am. Reference BK-1234.", ["create_booking"])
        return AgentReply(next(replies), ["update_booking"])

    return agent


# FALLBACK, off on purpose. The agent above is deterministic; the judge is not. If you need
# a take with no API key, pydantic-ai's FunctionModel is a Model instance and JudgeEvaluator
# accepts one, so adding this argument to the JudgeEvaluator(...) in tests/test_reschedule.py
# pins every verdict offline (import FunctionModel from pydantic_ai.models.function,
# ModelResponse and ToolCallPart from pydantic_ai.messages):
# model=FunctionModel(lambda *_: ModelResponse([ToolCallPart("final_result", {"passed": True, "reasoning": "ok"})]))
# The trade-off is the whole point of the page: the reasoning on camera becomes ours rather
# than a model's, and one fixed verdict passes every run — 3/3, not the 2/3 that shows a
# judge disagreeing with a reply. Use it to prove the plumbing, not to record.
