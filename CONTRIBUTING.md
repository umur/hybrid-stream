# Contributing to HybridStream

## ⚠️ TDD is mandatory. No exceptions.

### The only acceptable order of work:

```
1. Write tests  →  2. Confirm they fail  →  3. Implement  →  4. All tests green  →  5. Commit
```

Never write implementation code before tests exist for it.

---

## Test coverage requirements

| Requirement | Details |
|-------------|---------|
| Every public function | At least one test |
| Every error path | ValueError, KeyError, corrupted input, missing fields |
| All 11 operator state roundtrips | `get_state()` → `restore_state()` must be lossless |
| Cross-component flows | snapshot → MinIO upload → download → deserialize |
| Edge cases | empty state, None fields, max values, zero values |

## Test naming

```
test_{what}_{condition}_{expected_result}

# Good:
test_deserialize_corrupted_magic_raises_valueerror
test_snapshot_roundtrip_all_11_operator_types
test_dag_cycle_detection_raises_valueerror

# Bad:
test_snapshot
test_it_works
```

## Per-phase instructions to Claude Code

**Always two separate prompts — never combined:**

**Prompt 1:**
> "Write all tests for Phase N. Do NOT implement anything yet. Tests should fail."

**Prompt 2 (only after tests exist):**
> "Implement Phase N to make all tests pass. Run pytest and fix failures."

## Branch naming

```
phase/N-short-description
```

## PR requirements

- All tests must pass (`pytest -v`)
- PR description must include test count and pass/fail summary
- No `# TODO` left in implementation code (tests or docs are fine)
