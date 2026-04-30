# Reporting

`pytest-agent-eval` adds score information to pytest's standard terminal output and can optionally write a full markdown report.

## Verbosity levels

### Default (no `-v`)

Tests appear with the standard `PASSED`/`FAILED` status. No extra LLM eval detail is shown inline.

```
tests/test_booking.py::test_booking_flow PASSED
tests/test_booking.py::test_refund_flow FAILED
```

### `-v` (one verbose flag)

A score summary line is appended to each eval test's output section:

```
tests/test_booking.py::test_booking_flow PASSED
  ---- LLM Eval ----
  [3/3 runs, score=1.00 >= 0.80]
    Run 1 ✅
    Run 2 ✅
    Run 3 ✅
```

### `-vv` (two verbose flags)

Per-turn evaluator reasoning is included:

```
tests/test_booking.py::test_booking_flow PASSED
  ---- LLM Eval ----
  [3/3 runs, score=1.00 >= 0.80]
    Run 1 ✅
      All substring checks passed
      All tool call checks passed
    Run 2 ✅
      All substring checks passed
      All tool call checks passed
```

## The `--agent-eval-report` flag

Pass a file path to write a full markdown report after the session:

```bash
pytest --agent-eval-live --agent-eval-report=eval-report.md
```

## Markdown report format

The generated report has two sections: a summary table and per-transcript details.

The summary table lists each transcript with its run count, pass count, score, threshold, and pass/fail status.
The details section shows every run with turn-level evaluator reasoning.

## Configuring the report path

You can set a default report path in `pyproject.toml` so you do not need to pass the flag every time:

```toml
[tool.agent_eval]
report_path = "eval-report.md"
```

The command-line flag always takes precedence over the config value.
