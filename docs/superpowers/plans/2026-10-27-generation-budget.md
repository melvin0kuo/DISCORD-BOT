# Rolling generation budgets

Goal: bound repeated requests for varied long output without labeling ordinary long answers as misconduct.

Implementation: persist generation duration, generated characters (including discarded output), request count and stop outcome in a separate SQLite ledger. Evaluate both windows across all channels for each user before calling the model; cap the next stream by its remaining duration and characters. Existing per-user active-request guard prevents concurrent requests from overspending the allowance. Quota events are independent from abuse flags. Retain 30 days; audit repeated admission denials at most once per user per minute.

Defaults: 12 requests / 180 seconds / 16,000 characters in 10 minutes; 40 requests / 600 seconds / 48,000 characters in one hour. Existing per-request 120-second and 24,000-character ceilings remain upper bounds. Windows expire gradually; restart retains completed usage. Generation time includes model queue/tool waits. Usage begins at deployment; prior logs are not retroactively charged.

Steps:
1. Reproduce rolling-window, restart, identity isolation and aborted-output cases with failing tests.
2. Implement SQLite ledger and integrate admission, stream cancellation and finally accounting.
3. Verify the full suite, document thresholds, push and restart after the ongoing response finishes.

Limitations: this measures characters and wall time, not provider-billed tokens. A hard process termination before final accounting cannot preserve the unfinished request. Normal cancellation and timeouts are charged.
