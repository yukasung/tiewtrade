> **Superseded scope — 2026-10-07:** เจ้าของยกเลิกหลายกระเป๋า/sub-account
> ผลตรวจนี้เป็นประวัติเดิม ไม่รับรอง implementation ของบัญชีเดียว

# F-08 implementation validation and review — 2026-10-07

Baseline: `7efbbfb`; branch: `feature/f-08-sub-account-wallets`; working-tree review.
Requirements, plan and validation Approved. No F-08 commit/push/merge performed.

## Implemented behavior

Metadata-only wallet registry binds an owner's ACTIVE key with fresh TOTP. DB invoker
trigger/owner RLS/composite FK enforce six retained wallets and exact-key fingerprint
uniqueness across key rows/users. Delete locks the key before collecting wallet IDs,
retains the registry and clears key_id/digest. Create/bind/disconnect audit uses UUIDs
and shares the data transaction. Type changes fail closed; no replacement/trading/balance
capability is introduced. Populated downgrade refuses and retains immutable audit.

Selected TailAdmin source was adapted into shared controls/account layout. React18,
Vite6 and Node22 remain; Tailwind4.3.3 is scoped without Preflight/remote fonts/demo
runtime imports. Both panels share one account QueryClient. Delete invalidates both
exact owner queries; refetch failure discloses stale data. Old GET/POST completion
cannot contaminate a newly signed-in identity; mutation retries remain disabled.

## Validation evidence

- Backend: **1,510 passed, 0 failed/errors/skipped**, one opt-in venue_contract excluded
  by existing config; three inherited deprecation warnings. Real role/RLS/races/migration
  tests used disposable PostgreSQL. XML result counted independently.
- Frontend: **54 passed**, eight suites; lint/typecheck/build green.
- E2E: **8 passed** using actual API/DB/worker plus FakeVenue. Key creation, a new
  current-period TOTP, wallet persistence, deletion/disconnect/logout and mobile
  keyboard/backdrop focus observed; no browser pageerror or credential storage.
- Backend ruff/format/mypy/import contracts green. Regenerated OpenAPI and frontend
  types identical byte-for-byte. Docker images and Linux frontend production build
  pass; API health and UI proxy /api/health pass.
- Inspected [desktop](2026-10-07-f08-wallets/wallets-desktop.png) and
  [360px mobile](2026-10-07-f08-wallets/wallets-mobile.png) synthetic screenshots:
  readable Thai, labels/status/reason visible, one-column mobile fields and no overflow.

TDD before schema/storage/API/UI established missing-table/module/unclassified-route
failures, then green. E2E fixtures were corrected to wait for a current TOTP instead of
future code, reset shared auth-throttle test state through the real role, serialize
FakeVenue due scans, and use exact Thai locator names. No product safety rules weakened.

## Review findings and resolution

Independent API task and final whole-feature reviews inspected approved specs, code
and existing integration. No functional/security defect in F-08 was identified.
Coverage findings were fixed with actual HTTP tests for key-add TOTP replay,
recovery-login refusal, foreign wallet404 equivalence, shared TOTP quota, unchanged
GET session timestamps and DEBUG duplicate-failure log capture. UI tests now cover
DELETE-success/refetch-failure and old pending POST settling after identity switch.
360px evidence and shared sidebar spacing token were added.

Final F-08 spec/quality verdict: **PASS — no outstanding implementation findings**.
This verdict does not claim that unrelated inherited dependencies are vulnerability-free.

## Inherited dependency security backlog

Docker npm ci and npm audit found four vulnerable dev packages. Comparing baseline
and current lockfiles shows each version unchanged by F-08:

| Package | Version | npm audit severity |
|---|---|---|
| vitest | 3.2.4 | Critical |
| tinypool | 1.1.1 | Critical |
| source-map-js | 1.2.1 | High |
| @vitest/mocker | 3.2.4 | Moderate |

Primary advisories: [Vitest UI/API](https://github.com/advisories/GHSA-5xrq-8626-4rwp),
[Vitest mocker](https://github.com/advisories/GHSA-82fw-gwwq-j7x9),
[Tinypool](https://github.com/advisories/GHSA-85c8-ppgw-ccpr),
[source-map-js](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).
Vitest UI/API exposure is conditional; this project's script uses `vitest run`, not
its UI server. These packages remain a real maintenance risk, despite passing tests.
Remediation needs its own approved scope; no unrelated framework/test-stack upgrade
was performed in this feature. npm audit did **not** pass.

NC-21/NC-22 remain before any use of wallets for trading. Template purchase/license tier
is absent from supplied source; verify distribution terms before publishing. This
implementation makes no claim to confirm real account identity or entitlement.
