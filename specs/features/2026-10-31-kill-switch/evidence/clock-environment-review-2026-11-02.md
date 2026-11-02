# F-19 host/Docker clock environment review — evidence insufficient for a fix

Owner requested `เริ่มตรวจ clock environment` after NC20 Not Reproduced. Read-only
review of existing configuration/logs; no clock/settings changes, service restart,
new container, trading/workload, instrumentation, Git or deployment in this checkpoint.
The Date & Time pane was opened, but Computer Use access was denied on both attempts,
including the retry requested by the owner. No UI setting was read or changed.

## Findings

| Question | Evidence | Conclusion |
|---|---|---|
| Did host time synchronization operate? | `/etc/ntp.conf` names time.apple.com. Existing macOS `timed` logs record NTP receipts and apply activity at09:29:17,09:45:17,10:01:17 Bangkok. | **Confirmed operational NTP activity** during the surrounding period; current UI switch value remains unknown. |
| Did host log a time adjustment at the failure? | Inspected timed09:35–09:45 and extended09:12–10:10; no apply event at09:41:25. | **Not established**. The absence of a logged event is not proof no clock correction occurred. |
| Was there startup clock adjustment? | At09:13:17, timed records successful settimeofday with reported adjust=-0.701861382. VM startup is09:16:53, failure09:41:25. | Confirmed earlier host adjustment; **not time-aligned** to the failure. |
| Did sleep/wake or VM restart coincide? | pmset has no Sleep/Wake transition09:35–09:45. Caffeinate sleep-prevention assertions span09:37:12–09:41:27. Virtualization log records VM startup09:16:53, no restart near failure. | No supporting event in inspected logs. Do not select sleep/wake as the cause. |
| Were resources/architecture different? | Existing/current inventory: aarch64, Linux7.0.14-linuxkit, Docker Engine29.9.2, CLI plugin4.96.2; boot logs8CPUs/3064MiB configuration, actual VM memory3,043,373,056bytes. | Resource bounds match the approved profile. This does not establish clock stability. |
| Did ordinary task containers have explicit clock-setting privilege? | Relevant runner/PostgreSQL and currently running other containers: privileged=false, CapAdd=null. | No explicit privileged/SYS_TIME grant found in this inventory; not a complete audit of every process in the VM. |
| Do VM logs identify a time-sync actor? | Retained init logs around failure contain apiproxy/containerd/command/dns.leases components, no clock daemon events; virtualization/console logs do not identify a setter. | **Insufficient VM-side clock-setter telemetry**. |

The confirmed r3 recorder anomaly remains unchanged: source journal line3606->3607,
wall -16.857ms, monotonic +18.732250ms, offset difference -35.589250ms, adjacent to
BOOK failure. Both wall timestamps are UTC; this is not explained by formatting a
local timezone. That evidence does not identify whether the adjustment originated on
host, VM synchronization, or another guest timekeeping component. Failed guard arguments
were not retained in r3, and NC20's1203calls/0failures do not supply them retrospectively.

Current host automatic-time switch was not independently read: systemsetup requires
administrator access, its preference file was not available at the checked public path,
and Computer Use permissions were not granted. **No permission bypass was attempted.**
Operational NTP log evidence above is available despite that UI limitation; enabling
or disabling NTP is not selected as a remedy.

## Method and scope

- Read only selected Docker setting keys and safe Docker info/privilege metadata;
  no credentials/environment values persisted.
- Followed Docker's documented JSON init-log/component format. Filtered relevant
  clock/lifecycle messages; giant opaque configuration/feature payloads excluded.
- Queried existing macOS unified logs for timed/kernel/powerd in the failure window,
  then the existing timed startup/nearby NTP sequence. No logging level was enabled.
- Read pmset history and the existing VM virtualization startup log. No passive clock
  sampling loop or probe was run, and stopped validation DB/Redis stayed stopped.
- Saved selected events, limitations, scripts and hashes under
  `validation-artifacts/f19-set5-20261101/clock-environment-review/`.

Reference context: Linux distinguishes wall-clock UTC from monotonic intervals;
wall-clock adjustments are permitted by its timekeeping interfaces. This explains why
an anomaly is possible, **not** who caused this one. See [Linux timekeeping documentation](https://cdn.kernel.org/doc/html/latest/core-api/timekeeping.html).
Docker documents macOS VM daemon JSON logs at init.log with component identifiers:
[Docker daemon logs](https://docs.docker.com/engine/daemon/logs/).
A limited search of the current Docker release notes for clock/time-sync fixes did not
establish a version-specific remedy; this review does not recommend an update as a proven fix.

## Decision and next scope

No configuration defect or production/environment fix is proved by this review.
Do not disable synchronization, add future-time tolerance, increase resources/deadlines,
or rerun W1 on the assumption a generic restart/update fixes it. Existing Failed and
Not Reproduced results stay unchanged; V-20 Failed/Pending Full Validation.

Recommended next scope: proposed **NC-F19-21 clock-only host/VM comparison**. Capture
both clock domains simultaneously with bounded sampling and timing uncertainty, plus
existing host logs, without PostgreSQL/Redis/Paper workers or trading. It can localize
host versus guest clock discontinuities; it cannot certify W1 or guarantee reproduction.
The plan/validation proposal is reviewable before approving any new timed diagnostic.
Alternative: hand the retained evidence to the environment administrator and keep
validation blocked until an independently justified environment remedy is available.
