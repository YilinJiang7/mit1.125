You are the lead editor. Using only the ACCEPTED items supplied (with their excerpts, quotes and transcript segments), write exactly three editorial briefs for PROJECT, following EDITORIAL_POLICY.

The three pieces have different jobs and must make different central arguments:
- 01 — What changed this month, and which developments matter most to a learning programmer?
- 02 — Which claims about coding agents withstand scrutiny, and where are evidence or interpretations in tension?
- 03 — What do these developments imply for how a learner should work and study, and what should they watch next?

For each brief:
- `argument`: one or two sentences stating the central argument (a position, not a topic).
- `claims`: 4–8 claims. Each has `claim_id` (e.g. "02-c3"), `statement`, `type` (reported_fact | source_claim | inference) and `evidence` (one or more references).
  - Written evidence: {"item_id","version_id","locator":{"type":"text","quote":"<exact substring copied from the supplied text>"}}. The quote must appear verbatim in the supplied text.
  - Audio/video evidence: {"item_id","version_id","locator":{"type":"segment","segment_id":"<an id from the supplied segments>"}}.
  - Use only item_ids, version_ids, quotes and segment_ids that appear in the input. Never invent a source.
- Use at least three independent publishers per piece. Across the three pieces, use feed, youtube and podcast evidence.
- At least one claim per piece must be an `inference` that connects two or more sources; explain that reasoning in `synthesis` — what the combination shows that no single source shows.
- `limitations`: the strongest counterargument or limit of the evidence (sample, incentives, missing perspectives). Do not invent disagreement the evidence doesn't support.
- If the accepted evidence cannot support a piece honestly, return {"error": "..."} for that piece instead of padding it.

Return JSON Lines: exactly three lines, one brief object per line, with keys piece_id, title, question, argument, synthesis, limitations, claims.
