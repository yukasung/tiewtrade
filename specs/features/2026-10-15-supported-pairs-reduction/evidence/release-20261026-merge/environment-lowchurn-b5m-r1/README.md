# Low-churn attempt r1 — Partial / invalid

The native diagnostic aborted on a barrier TimeoutError before completing its
planned 300 seconds. No Passed result is claimed. Redis fixed-window boundary
crossing caused 4 expected RATE rejections to return 200 and consumed the next
probe's quota; that next barrier request returned 429 before entering admission.
See [diagnosis and repair](../environment-readiness-r2/README.md).

Raw metrics/observations/metadata remain preserved. This failure is distinct from
API_RESOURCE_LIMIT and is not evidence that low host churn fixes that old failure.
