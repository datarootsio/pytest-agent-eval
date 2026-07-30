from dataclasses import dataclass
from pathlib import Path

import pytest

from pytest_agent_eval import AgentReply

# Five perfectly good confirmations of the same booking. The 2nd and the 5th happen not
# to contain the word the naive assert picked.
REPLIES = [
    "Booking confirmed for tomorrow at 10am, ref BK-4415.",
    "You're all set for tomorrow at 10am, ref BK-4417.",
    "All confirmed for 10am tomorrow, ref BK-4419.",
    "Slot confirmed, see you at 10am, ref BK-4421.",
    "Done! Your 10am slot is reserved.",
]

# The typed command is five SEPARATE pytest processes, so which reply comes next has to
# outlive the process. An in-process counter would reset and all five would draw REPLIES[0].
COUNTER = Path(__file__).parent / ".cast-counter"


# A class rather than a closure: pytest prints the fixture's repr above the failing
# assert, and `<function agent.<locals>.call at 0x10a3e3600>` would put a fresh hex
# address on camera in every take.
@dataclass
class Agent:
    reply: str

    # ARG002 rather than the ignored ARG001 only because this is a method: the agent
    # contract takes the history whether or not a stub reads it.
    async def __call__(self, history):  # noqa: ARG002
        return AgentReply(self.reply, [])


@pytest.fixture
def agent():
    run = int(COUNTER.read_text()) if COUNTER.exists() else 0
    COUNTER.write_text(str(run + 1))
    return Agent(REPLIES[run % len(REPLIES)])
