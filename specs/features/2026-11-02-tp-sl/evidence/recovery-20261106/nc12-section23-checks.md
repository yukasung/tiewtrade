NC12 §23 implemented/checked,2026-11-07. Optional synchronous test-worker engine
factory defaults to the original role factory lookup. Restored recovery constructs
independent worker-owned target ENGINE/ENGINE_SCAN using scoped role URLs during
synchronous construction only; source env restored before any await. Pool/credential/
scheduling/financial defaults unchanged. Verify compares full source canonical data
(including extensions) before/after target recovery and requires source_unchanged.

Targeted125unique cases covered:124passed in shared suite; the empty-source test
was run after a seeding test and failed its isolation prerequisite, then passed on
a separate fresh DB. Six routing/digest cases rechecked after test import correction
passed1.66s; empty prerequisite passed1.65s. Real two-DB SELECT current_database
proof for both roles plus normal stop/error/cancel cleanup and constructor/config
restoration passed. Scoped Ruff/format/mypy passed3files. Preserve initial logs.
No production change; prior long workload/safety evidence remains applicable to
unchanged default worker path. Required CI/full-regression not replaced by these
partitioned local checks; database-empty cases require isolated fixture execution.

Next: one approved fresh-source/fresh-target W4 with same preflight/fixtures/
backup/restore/60s recovery criterion and strengthened source-unchanged proof,
estimated5–10min. Do not repeat W1/W2/overflow/shortW3. Failed/incomplete stops;
pass closes this local integrated validation checkpoint only, with existing
review/CI/4h Release/bot/notification/Live obligations still separately pending.
