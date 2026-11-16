# Retired lessons

Lessons /tidy took out of the topic files: a check now says all of it, or I settled a contradiction against it. Kept
here, never deleted; their IDs are never reused (docs/lessons/README.md).

| Date | ID | Lesson | Why retired | Now |
| --- | --- | --- | --- | --- |
| 2026-11-16 | B-02 | Every build gives the same result twice | `pbik build` writes only changed files and the regression suite checks a second build prints "No changes" | tools/regression/regress.py; .claude/rules/pbik.md (idempotent) |
| 2026-11-16 | B-07 | Rename fields per visual with displayName | `pbik build` writes `displayName` per projection; nothing left to remember | layout `displayName` on a binding (layout-schema.md) |
