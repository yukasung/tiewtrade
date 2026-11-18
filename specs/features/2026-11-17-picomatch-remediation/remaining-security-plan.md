# Picomatch LP04 publication
สถานะ: Approved — owner approved combined plan and NC-PM-IDENTITY-01.
The owner reviewed and approved the exact dependency registry diff on 2026-11-18.
See [approved diff](evidence/remaining-integrated/proposed-exception.diff).
Use the verified LP04 tarball for all current build consumers, preserve its upstream
version and license, and verify its archive, parser, provenance and installed identity.
Scan both original lockfiles plus the verified CycloneDX component with the pinned OSV.
Apply normal policy to every finding, binding the local finding to the archive digest.
Copy the installed archive into the Docker build before the frozen npm install.
Run targeted policy tests and required CI, then merge the reviewed head and verify main.
Retire the exception when a compatible official fix is verified. Reassess if callers change.
