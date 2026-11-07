

NC12 §15 implementation checkpoint — 2026-11-07: owner approved A. Added NC12-only
owned-pool inventory/periodic samples/pre-disposal return checks, reusing PoolEvidence.
Production and other profile predicates unchanged. Affected regression:214 passed,
4 initial failures corrected; scoped rechecks35/35 passed. Ruff/format and scoped
mypy passed. Existing production50 safety checks remain applicable. One approved
fresh-DB W1 is next; no new timed result yet. Historical §14-v2 W1 remains Failed.

Checks: regression XML/logs and recheck XML/logs in this directory; mypy log retained.
