"""Short host-only observation before an environment A/B; never workload credit."""

import json
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from tests.services.indicator_builder.profile_capacity_host_audit import counter


def capture(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    samples: list[dict[str, Any]] = []
    started = monotonic()
    for tick in range(16):
        sleep(max(0, started + tick * 2 - monotonic()))
        raw = subprocess.check_output(["vm_stat"], text=True)
        samples.append({"at": monotonic(), "utc": str(datetime.now(UTC)), "vm_stat": raw})
    churn = []
    swapin = 0
    swapout = 0
    for index in range(1, len(samples)):
        left, right = samples[index - 1], samples[index]
        elapsed = float(right["at"]) - float(left["at"])
        before, after = str(left["vm_stat"]), str(right["vm_stat"])
        pages = sum(
            counter(after, name) - counter(before, name)
            for name in ("Compressions", "Decompressions")
        )
        # This machine's observed page size is 16 KiB; fail if it changes.
        assert "page size of 16384 bytes" in before and elapsed > 0
        churn.append(pages * 16384 / elapsed / 1024**2)
        swapin += counter(after, "Swapins") - counter(before, "Swapins")
        swapout += counter(after, "Swapouts") - counter(before, "Swapouts")
    report = {
        "diagnostic_only": True,
        "seconds": monotonic() - started,
        "samples": samples,
        "median_churn_mib_s": statistics.median(churn),
        "max_churn_mib_s": max(churn),
        "swapin_pages_delta": swapin,
        "swapout_pages_delta": swapout,
        "swap_usage": subprocess.check_output(["sysctl", "vm.swapusage"], text=True),
        "pressure": subprocess.check_output(["memory_pressure"], text=True),
    }
    output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    capture(Path(sys.argv[1]))
