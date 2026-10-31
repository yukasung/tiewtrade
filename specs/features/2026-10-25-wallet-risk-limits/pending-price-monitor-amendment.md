# F18-R20 — Published price progress as a monitor scheduling hint

สถานะ: Approved — owner approved R20 on 2026-10-28

## Evidence and narrow hypothesis

R19 ordering-only experiments failed and were rolled back. They did not change
eligibility: a successfully evaluated owner remains excluded until due_at even
when a newer price frame is already committed. Trace for input4418 proves this:
owner cursor4417, new input at t=0, next scan at~+.158s just before its200ms due
boundary skips the owner; it cannot enter the queue until~+.783s. R19 can only
sort owners AFTER selection and cannot recover that skipped opportunity.

Host/Docker cleanup reduced disk paging substantially. Original4-slot comparison
still failed405late/max1.580120s; R19 first-after-restart failed879late/max1.940027s.
This motivates changing only the eligibility hint, not adding slots or weakening
any SLA. It remains a hypothesis requiring measurement, not a promised pass.
Full trace and failures remain in evidence/m5-final-candidate.md.

## Proposed implementation

1. Start from restored original UUID-order/page100, monitor4 runtime. Keep all
   current due_at/NULL/evaluation-request predicates. Add one OR predicate:
   `o.cursor < (SELECT watermark FROM risk_price_publication)`.
   PostgreSQL's single scalar subquery reads the committed singleton watermark
   within the same statement snapshot. No extra query or publication fence.
   NULL/missing publication makes only this new predicate non-true; existing
   due/hint paths remain, and actual replay still fails closed as appropriate.
2. This schedules an owner during its200ms cooldown ONLY if it has committed
   price frames not yet replayed. No-input/source-expiry monitoring retains the
   existing due_at schedule. Keep original UUID cursor/wrap, page100, one attempt
   per candidate/sweep,4transactions/pool4, blocking owner100ms,statement700ms,
   inter-round20ms,frame100/boundary20 budgets and all request/stop pools.
3. The scanner currently lacks these two column grants. Add migration0058 after
   0057 granting ONLY SELECT(cursor) on risk_owner_state and SELECT(watermark)
   on risk_price_publication to tiewtrade_engine_scan. Downgrade revokes exactly
   these new grants. No new table/index/row/financial writer or security-definer
   function. Do not grant books, balances, positions, price payloads or writes.
4. The hint is never authority. Existing owner lock/RLS session, fresh snapshot,
   contiguous/checksummed frame replay, source readiness, financial/PnL/Money
   logic, latch/stop rules and financial publication fences are unchanged. It
   cannot create an order or mutate funds. Keep R9/R10/R11 disabled as in baseline.

## Tests and acceptance

Reuse run_risk_monitor_round, actual ENGINE_SCAN role/session and existing
scheduler/publication fixtures. Test:
- Future due + committed watermark ahead selects/replays the owner without
  changing due_at manually; equal/current cursor and no hint stays excluded.
- Uncommitted publication is not a hint; after commit it becomes eligible.
- Existing explicit hints, NULL/uninitialized and due owners still progress;
  UUID page/wrap and transaction concurrency bounds remain intact.
- Missing/corrupt/stale inputs remain unavailable; repeated hint processing
  cannot duplicate breach/stop effects or authorize opening prematurely.
- Exact new scanner column grants, rejected financial/payload/write access,
  upgrade/downgrade restoration and backup/restore grants on0058.
Run affected scheduler/concurrency/replay/stop/financial-fence tests and static
checks before any load. No automated Live orders.

Compare once using the same frozen dataset/resources/default flags and passive
instrumentation, with the same VM-restart precondition as the recorded baseline.
Record source cadence, host paging/loop lag, every-input latency and owner/stop/
request progress. Extra eligible owners may increase CPU, DB work or lock
contention; if it does not improve the identified delay, revert the runtime hint
and migration after preserving evidence. Do not increase concurrency/resources.

Only a qualifying preflight proceeds to the existing final-drain/60s-cycle proof,
then W1(600s),W2(300s),W3(1800s),0058W4 and final regression/review under the approved
closure plan. Preserve all historical failures, deadlines, rates and oracle
criteria. V22/V23 remain Pending Dependency; no Completed/activation claim.

## Approval boundary

R19 authorized order within an already eligible page; this changes eligibility
and adds two narrow scanner grants, so it is a new method. plan.md:301 requires
“ขอ plan amendment ก่อนเปลี่ยนวิธี”; AGENTS.md forbids implementing an altered
approved method before approval. R20 implementation followed owner approval; current safety/measurement evidence is in M5.
