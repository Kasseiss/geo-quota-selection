# Bounded migration accounting

`code/v2_migration_budget.py` is a standard-library-only helper. It never creates,
copies, moves, deletes or rolls back payload files. Its caller must first confirm
that every other project writer has stopped and must use the true whole-project
budget root. It does not protect against arbitrary concurrent external writers.

```python
with MigrationBudget(root, allowance, 2_000_000_000, logical_bytes) as budget:
    budget.check(known_bytes)       # No charge and no filesystem scan.
    budget.charge(known_bytes)      # Before creating/copying/appending bytes.
    write_known_bytes()
    # Same-root MOVE has zero logical growth, so no positive charge.
ledger = budget.ledger
```

The allowance must include every known COPY, exclusive-file creation, append,
metadata write and the required reproduction reserve (including its 4 MB margin).
Reserving allowance is not an actual charge: `charged` starts at zero. A metadata
replacement charges the entire new temporary file before writing, without
subtracting the old file. Failed and partial writes retain their full charge.

`start()` (also context entry) scans once and requires
`baseline + allowance < cap`. `check(extra)` requires both
`charged + extra <= allowance` and `baseline + charged + extra < cap`, without
changing the ledger. `charge(n)` performs that check and adds the charge atomically
within this process. Nested active budgets, including different roots, are refused.

`finish()` scans once more and requires `final < cap` and
`foreign_delta = final - baseline - charged <= 0`. Positive unaccounted net growth
fails closed even if the cap is not reached. A negative delta can reflect failed
writes retaining their charges or replacement of existing bytes. It is not credit
for future allocations. The returned ledger contains baseline, allowance, cap,
charged, final, foreign_delta, passed, state and scan count. The object retains its
ledger after any failure; callers can persist it in their existing receipt flow.
The helper itself writes no ledger file and therefore adds no hidden bytes.

Context exit scans even when the body raises. The body exception propagates if
the final budget check passes; a failed final check raises its own exception with
the body exception retained as context. No files or charges are rolled back.
Accounting success describes storage verification only, not migration success.
The two scans verify net logical growth; untracked writes offset by deletions
cannot be identified. The required stopped-writer condition remains essential.

Run the five synthetic fixture tests with the current Python:
`python code/test_v2_migration_budget.py`. They cover strict cap boundaries,
up-front reservation, intermediate refusal, exactly two scans across many writes,
move/replacement accounting, foreign growth, exception preservation, nesting and
failed-scan cleanup. They do not migrate actual project files.
