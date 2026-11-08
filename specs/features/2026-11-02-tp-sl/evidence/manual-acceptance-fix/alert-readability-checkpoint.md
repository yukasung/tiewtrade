# Shared warning readability correction — 2026-11-08

Owner reported TP/SL panel unreadable after functional manual observations.
Root cause: unlayered .app-theme [role="alert"] legacy error skin overrode the
shared template warning background, while its children used dark-mode text.
Shared Alert now marks its root ui-alert; legacy skin excludes this marker.
No financial, authorization, status, copy, layout, API, or owner state changes.
Source reference: references/admin-template/src/components/ui/alert/Alert.tsx.

Checks: PaperTradePage/ManualOrderForm33passed; typecheck and scoped Alert ESLint
passed. Isolated browser loaded actual Vite Alert module/theme without owner auth
or API actions: warning/error/success/info light+dark computed styles recorded in
f17-alert-readability.json. Warning differs from legacy error background; dark
error retains template transparency. Plain legacy errors retain their existing
style. Dark screenshot visually inspected; screenshot artifacts include both themes.
Temporary preview removed after verification. No workload or manual round repeated.

This corrects the observed visual blocker; no change to prior functional evidence.
Not a new owner-browser visual confirmation or required CI pass. Owner may refresh
local read-only view; all gates remain off. Required final-candidate review/CI and
Release dependencies remain pending. No commit/push/merge.

Changed source SHA256:
{
  "frontend/src/components/ui/Alert.tsx": "d00db0d86b2288cd3acfa3ab81e00d1b48a1341669b2d9f98dfdfec005e400fa",
  "frontend/src/styles/admin-theme.css": "5924e879283d98ae9150af56f85f4a04d3f242d647c67e2a0d119f4d244e1379"
}
