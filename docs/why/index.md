# Why pytest-agent-eval

LLMs are probabilistic. The same prompt, the same code, the same commit can pass one run and
fail the next, and a plain `assert` was never built to answer a question about a distribution
from a single sample. `pytest` is still the industry-standard way to test Python, so rather than
inventing a new framework, this plugin extends it: the same `assert`, the same `pytest ...`, the
same CI job, but with the pieces a probabilistic system actually needs: repeated runs,
thresholds, and checks on what an agent *did* rather than only what it *said*.

This is what we'll be looking at:

- [Why write tests](why-tests.md): tests aren't about correctness, they're about *change*
- [The anatomy of a test (in pytest)](what-is-a-test.md): the properties the `assert` relies on
- [Pytest meets LLMs](why-it-breaks.md): why those four properties fail the moment the code under test is an agent
- [Runs, thresholds, tiers](runs-and-tiers.md): sample the distribution, then assert in tiers
- [Asserting on behaviour](tool-calls.md): going beyond LLM-as-a-Judge
- [LLM as a judge](judges.md): the rubric, what it buys, and what it costs
- [Gates and statistics](gates.md): aggregates, and what three runs can and can't tell you
- [The contract](one-contract.md): the one function signature every adapter satisfies
- [Agents to check agents](agents-author-evals.md): how can we help the agent writing evals
- [What else is in the box](whats-in-the-box.md): voice, parallel runs, reports, and the plain Python API

## Go deeper

- [Getting started](../getting-started.md): install, configure, and run your first eval
- [Examples](../examples.md): a runnable project per feature
