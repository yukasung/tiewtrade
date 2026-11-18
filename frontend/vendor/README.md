# Picomatch LP04 source candidate

This directory is part of a **source-verified remediation candidate**. It is not an
official patched picomatch release and is not approved for release merely by existing here.

- `picomatch-4.0.7-lp04.tgz`: reproducible local prototype, package name/version unchanged.
- `picomatch-4.0.7-upstream.tgz`: integrity-verified original archive, retained only for
  byte-for-byte provenance comparison; not an installed dependency or browser asset.
- `picomatch-4.0.7-lp04.patch`: exact reviewed diff against original `lib/parse.js`.

Both archives retain upstream MIT LICENSE and package metadata. Authoritative identities
are in `tools/security/trusted-sources.json`. The security adapter validates archive paths,
member types, names/content scope, manifest/license, parser and exact unified diff without
executing/extracting archive code. Configuration identity binds those bytes.

LP04 intentionally literalizes some risky repeated wildcard extglobs. Finite matching
and installed-toolchain proofs do not certify global ReDoS safety or all caller options.
The pinned scanner queries the upstream advisory through a hash-bound SBOM. The owner
approved the exact LP04 exception on 2026-11-18. Required CI evaluates publication.

See `specs/features/2026-11-17-picomatch-remediation/remaining-security-plan.md` and its
`evidence/remaining-integrated/` checkpoint before changing or deploying this candidate.
