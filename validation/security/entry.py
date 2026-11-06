import os
from pathlib import Path
Path(os.environ["RUNNER_TEMP"], "security-probe-python").write_text("executed")
