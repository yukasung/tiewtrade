"""External telemetry for acceptance; does not replace/instrument the API loop."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep


def collect(output: Path, container: str) -> None:
    output.mkdir(parents=True, exist_ok=False)
    started = monotonic()
    try:
        for tick in range(1080):
            sleep(max(0, started + tick * 5 - monotonic()))
            host = subprocess.run(["vm_stat"], capture_output=True, text=True, check=False)
            vm = subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "sh",
                    "-c",
                    "cat /sys/fs/cgroup/cpu.stat; cat /proc/pressure/cpu; "
                    "cat /proc/1/schedstat; head -1 /proc/stat",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            with (output / "samples.jsonl").open("a") as history:
                history.write(
                    json.dumps(
                        {
                            "utc": str(datetime.now(UTC)),
                            "host_monotonic": monotonic(),
                            "host_vm_stat": host.stdout,
                            "vm_exit_code": vm.returncode,
                            "vm_cpu_scheduling": vm.stdout if vm.returncode == 0 else None,
                        }
                    )
                    + "\n"
                )
    except KeyboardInterrupt:
        pass
    finally:
        (output / "collector.json").write_text(
            json.dumps(
                {
                    "method": "external_vm_stat_and_docker_exec_read_only",
                    "interval_seconds": 5,
                    "elapsed_seconds": monotonic() - started,
                    "api_entrypoint_replaced": False,
                    "acceptance_credit": False,
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    collect(Path(sys.argv[1]), sys.argv[2])
