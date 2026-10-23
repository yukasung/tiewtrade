# Proof cleanup — 2026-10-24

Owner requested removal of disposable files from the self-hosted CI experiment.

- Validated the recorded UID/GUID, stopped proof VM, exact owned runtime paths,
  matching VM template, and detached/empty proof PF rules before deletion.
- Deleted the named proof VM, its `.lima` directory, Lima download cache,
  copied home template, and the three task runtime directories (including keys).
- Uninstalled Lima 2.2.1; no installed Homebrew dependents were reported.
  Automatic dependency removal was disabled.
- Account/home archival failed with macOS `Operation not permitted` while
  renaming `/Users/tiewtrade_ci`. The disabled account and residual home remain;
  the GUID-named archive directory was created but the home was not moved.
  No broader OS access was requested. Identity manifest remains unchanged.
- Repository code/evidence and existing development resources were preserved.
- Cleanup is partial, not a successful isolation validation or feature completion.

The cleanup helper is not safe to rerun after this partial execution: its
preconditions require the deleted VM and runtime directories to exist.
