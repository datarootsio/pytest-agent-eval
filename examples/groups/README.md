# groups

Group-level quality gates: `edge_case` fails on purpose, but the `booking` group's 0.5 threshold absorbs it, so the run exits `0` while the failure stays visible in the group summary.

```bash
pytest --agent-eval-live; echo "exit: $?"
```

See the [group thresholds docs](https://datarootsio.github.io/pytest-agent-eval/latest/groups/) for membership, `must_pass`, and override semantics.
