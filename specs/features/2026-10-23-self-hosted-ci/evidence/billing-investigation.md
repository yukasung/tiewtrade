# GitHub-hosted fallback investigation — 2026-10-24

Historical snapshot before the public-repository rerun. Superseded for current
status by [closure-checkpoint.md](closure-checkpoint.md): attempt 3 passed all six
jobs. The original account billing cause remains undetermined.

Read-only checks for account `yukasung`, repository `yukasung/tiewtrade`.

- Latest CI run remains 39972554569, attempt 2, merge SHA
  `51f0e2700e5c478e5b13b52f2cedcff2f6961d8d`, Failed.
- Check 120481110077 annotation says job did not start because recent account payments
  failed or spending limit needs increasing. This does not distinguish quota exhaustion
  from an account/payment restriction. Do not conclude that waiting for quota reset fixes it.
- The preceding push and PR runs 39969738698 / 39969745616 both succeeded on the same
  head `b79736cfc24da9e30a4397f18b7d435b008313d9`. Workflow currently triggers on all pushes
  and PRs; this is concrete duplicate execution evidence for the approved trigger reduction.
- This repository currently has 23 artifacts totaling 18,037 bytes and 2 caches totaling
  43,499,048 bytes. These API values are not account-wide billed storage or monthly usage;
  no artifacts/caches were deleted.
- Billing API returned 404 with an explicit missing `user` OAuth scope diagnostic.
  Current CLI login works for repository/workflow access. No token scope expansion was made.
- Browser connector reported no available browser; native Chrome access was denied because
  Computer Use permissions are not granted. Billing UI could not be read.

Required next evidence: account Billing usage/allowance/reset date, budgets and any payment
restriction banner, with payment details redacted. Until available, root cause remains
undetermined. No paid spending, rerun, workflow changes, commits or pushes were performed.
Existing Mac proof code/evidence is retained; this investigation does not certify its isolation.
