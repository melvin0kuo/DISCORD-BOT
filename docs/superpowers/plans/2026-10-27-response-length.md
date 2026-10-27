# Bound individual response length

Accepted scope: prevent unreasonable one-shot generation, including varied numbered sound subtitles, without treating length as misconduct.

Approach: explicit oversized generation requests return a batching suggestion before model admission. Input document size is not output size. Supply request-specific instructions and enforce character/nonempty-line limits on each streamed chunk before delivery. General/story/subtitle limits are 4,000 characters and 80 lines; technical/document limits 8,000 and 160. The rolling generation budget remains an independent smaller bound when depleted. Store oversized_request or response_length audit events independently of abuse flags. The classifier is heuristic; runtime limits still apply when phrasing bypasses preflight.

Validation: first reproduce oversized request and varying-line failures; add input-document-size and normal technical budget regressions; implement; run full suite; push and restart.
