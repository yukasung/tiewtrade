const fs = require("node:fs");
const path = require("node:path");
fs.writeFileSync(path.join(process.env.RUNNER_TEMP, process.argv[2] === "lifecycle" ? "security-probe-lifecycle" : "security-probe-javascript"), "executed");
