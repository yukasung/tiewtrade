# NC-F19-24 ephemeral tracefs diagnostic — 2026-11-02

Status: **Incomplete; stopped without a repeat**

This evidence is diagnostic only. `acceptance_result=false`; it does not pass or regrade
V-20 and does not identify a clock setter.

## Implementation and controlled checks

Added a stdlib-only observer that reuses NC21's bracketed clock sampling and supports:

- exact CAP_SYS_ADMIN/no-new-privileges/seccomp gates and bounded LSM evidence;
- namespace-local tracefs mount, private UUID instance, mono trace clock and the eight
  approved syscall entry/exit events;
- paired/redacted events, clock ID only for `clock_settime`, return/timing identities,
  64KiB perCPU buffers and10,000-record/16MiB caps;
- per-CPU drop/overrun checks,10Hz wall/monotonic samples and conservative classification;
- exact-instance cleanup plus namespace unmount on every handled exit.

Final controlled result: **45 passed**, zero skips. Ruff check, Ruff format check and mypy
on the NC21/NC24 observer and test files passed. Cases cover success/failure/non-realtime,
missing pairs/identities/events, mount denial, capability/confinement/LSM gaps,
redaction, caps, drops/overruns, output failure, observer failure and cleanup-before-mount.
No test mounted tracefs or used trading/database services.

The first image-build command used an invalid local `FROM sha256:...` reference and failed
before producing/running a container. The corrected Dockerfile uses the local tag only
after checking its ID equals the approved base digest. It copies just the two observer
files and installs nothing.

## One authorized execution

Container `tiewtrade-f19-nc24-clock-r1` used the unchanged8CPU/3,043,373,056-byte VM,
approved base digest and derived image
`sha256:c068fb58a1f0c5b8044e2848448953088ee95339898e3403a5abb670188a91b1`.
Inventory: privileged=false, host PID, network none, read-only root,0.1CPU/64MiB/32PIDs,
cap-drop ALL plus CAP_SYS_ADMIN only, no SYS_TIME/SYS_PTRACE, no-new-privileges, default
seccomp, bounded tmpfs and no bind mount/Docker socket/application env. Docker added its
LinuxKit `label=disable` entry; no AppArmor/seccomp override was requested.

The container ran08:17:18.794130→08:17:24.566185 UTC (**5.772s**), exited2 and was not
OOM-killed. It emitted no stdout because the executed observer wrote its result only into
container tmpfs; that tmpfs was unavailable after exit. Consequently its exact failure,
mount/trace stage, records and cleanup result were not captured. This is a harness evidence
transport defect, and the execution is **Incomplete** regardless of what occurred inside.
It was not repeated.

Executed observer source is frozen in the artifact directory with SHA-256
`e3dea37d2ac563fd41856edc0e60071b65ee1185e62c004f2cf31503c0aa63e3`.
That source reads `/proc/self/attr/current` before calling `mount_tracefs()`.

## Single cleanup-only helper

The one authorized cleanup-only helper used the same security/resource profile and exact
instance `f19_nc24_202611020756abcd`. It ran08:18:29.049842→08:18:34.009047 UTC
(**4.959s**), exited2/noOOM and captured:

- effective capability `0000000000200000` (CAP_SYS_ADMIN only);
- `NoNewPrivs=1` and `Seccomp=2`;
- `OSError` before mount while reading `/proc/self/attr/current`.

Because the helper stopped before mounting tracefs, its default `instance_cleanup=true`
was a no-op value, not proof that an earlier instance was absent. The executed observer
has the same pre-mount LSM read and the same container profile, which strongly supports
the same pre-mount failure branch, but its missing result prevents direct proof. Cleanup
must therefore remain **unverified**, as required by the fail-closed plan. No second helper
or alternative inspection was used.

## Post-run harness correction (not executed)

After preserving the failure, the observer was corrected to:

- emit the bounded sanitized result to stdout as well as tmpfs;
- classify a missing LSM evidence file explicitly as
  `NC24_LSM_EVIDENCE_UNAVAILABLE`; and
- refuse to report cleanup success when a cleanup-only helper never mounted tracefs.

Regression and static checks were rerun to the final45-passing result. This corrected
source was **not** used for another mount or diagnostic. Final source/image hashes,
executed source, container states and sanitized results are retained under
`validation-artifacts/f19-set5-20261101/nc24-clock-setter/`.

NC19 production and scheduler-test hashes still exactly match its measured candidate;
no production/API/schema/financial/scheduler code or safety evidence changed.

## Conclusion and next gate

Classification: **Incomplete**. No setter is Confirmed/Candidate/Not Reproduced, no90s
clock observation is valid, and cleanup is unverified. No Docker/NTP setting, service,
trading worker, PostgreSQL, Redis, workload or W1 was changed/run. V-20 stays
**Failed/Pending Full Validation**; W2/W3/W4 remain Not Run.

Per the approved stop rule, further cleanup inspection, mount attempt, environment change,
alternative tracer or W1 requires a new owner-approved amendment. The evidence gap is now
the unavailable LSM profile plus the lost first-run result; do not rerun unchanged code.
