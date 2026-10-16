# Editorial Policy — Apprentice Mode

Version: **v2 (2026-10-14)** — revised after Yilin's review of live run 1 (`reviews/run1_editorial_review.md`). v1 is preserved at `reviews/editorial_policy_v1.md`. Any revision gets a new version number, a dated changelog entry at the bottom, and a new pipeline run so the before/after outputs stay comparable.

Reader: a student in their first one or two years of programming who already uses coding agents but cannot yet reliably judge their output. Every decision asks: **would this change what that reader delegates, checks, learns or avoids this week?**

## 1. Audience relevance

Accept material that does at least one of these:

- Changes what a learner can safely delegate to a coding agent (new autonomy, sandboxing, review, testing or permission features; new failure modes).
- Gives evidence about productivity, correctness, security or **learning** effects of using agents.
- Shows a concrete workflow, failure or habit a beginner could copy or avoid.
- Shows how instructors or courses are responding (policies, assignments, assessment).
- **Explains cost, speed or token usage in terms a student can use** — what a task actually costs, why bills grow, how to keep usage under control. Beginners care about this and have little intuition for it. *(added in v2)*

Reject material that is mainly about: benchmark leaderboards with no coding-agent consequence, funding or valuations, enterprise sales, or general AI opinion with no concrete coding-agent content. Reject items that assume expert knowledge and offer nothing a learner could act on.

## 2. Freshness

- The pipeline already removed anything published outside the 30-day window or without a date. Do not override that.
- A recent item that discusses an **older** event is allowed only if it adds something newly reported or learned (new data, a follow-up, a correction). Say what is new in the reason.
- A re-upload, repost or refreshed date on unchanged content is not a new development.

## 3. Credibility — judge the evidence for the specific claim

Reputation, popularity, view counts and the model's own confidence are **not** evidence. For each item ask:

- What is the strongest claim, and what evidence is shown for it (data, method, reproducible demo, first-hand experience, or just assertion)?
- Is the speaker in a position to know? (Ran the study, built the feature, used the tool on real work.)
- Classify claims: **reported_fact** (verifiable event or number with a source), **source_claim** (what someone asserts, e.g. a vendor's "55% faster"), **inference** (our own reasoning across sources).
- **Describe the source accurately.** Say whether the speaker is an expert, a vendor employee, an educator or a learner. An expert's workflow shows what an *expert* can delegate; say so before suggesting a beginner can do the same. *(added in v2)*
- arXiv preprints are not peer reviewed: note sample size, who the participants were (students vs professionals), and whether the task resembles real coursework.
- Several outlets repeating one announcement = **one** underlying claim, not corroboration.

## 4. Commercial incentives

Vendor blogs, launch videos and vendor employees on podcasts are usable evidence — including on efficiency, speed, cost and performance, which are in scope — **provided the commercial interest is stated**:

- Every number or performance/productivity/cost statement from a vendor (or a vendor employee) is typed `source_claim` and attributed by name ("GitHub says…"). Never `reported_fact`.
- Pair it with an independent practitioner or research source that tests the same claim **when one exists**; if none exists, say the claim is unverified.
- Influencer and creator channels (e.g. developer YouTubers) are practitioners, not vendors, but have an attention incentive: weigh the demo or reasoning they show, not their headline. If they also sell a product, say so.

*(v1 said vendor numbers "should be paired" with a test source; v2 keeps vendor efficiency/cost content in scope and makes the labelling rule explicit.)*

## 5. Novelty

Prefer items that add something not already in the accepted set: a new fact, a new kind of evidence, or a new perspective. When two items say the same thing, accept the one closest to the original evidence and reject the other as duplicate coverage. Two posts from one publisher about the same feature count as one.

**Publisher cap (v2):** accept at most **3 items per publisher** per run. If more qualify, keep the 3 closest to original evidence and defer the rest with the reason "publisher cap".

## 6. Diversity of perspectives

Across the accepted set, aim to include: vendor/commercial, independent practitioner, research, and educator or learner perspectives, and all three input types (feed, youtube, podcast). If a perspective is missing (e.g. no student voices, no non-US sources), say so in the briefs instead of pretending balance.

## 7. Uncertainty, conflict and unsupported claims

- Piece 02 actively looks for at least one place where sources disagree or measure different things. If there is none, it says so plainly. *(v2 — the README asks piece 02 "where are the evidence or interpretations in tension?" and forbids manufactured disagreement.)*
- When sources conflict, first check whether they measure different things (different users, tasks, time frames). Explain the difference before declaring a winner.
- Do not manufacture disagreement where the evidence agrees.
- A claim with no shown evidence may be reported only as "X claims …", never as fact, and never as the basis of a recommendation.
- State remaining uncertainty explicitly; "we don't know yet" is an acceptable conclusion.

## 8. Decision rules

- Judge audio and video on the whole transcript sample, not the opening minutes; ignore sponsor reads. *(v2)*
- **accept** — relevant, has evidence a reader can inspect, and serves at least one of the three pieces (normally **one, at most two** — so the three pieces stay distinct). Name the piece(s): 01 what changed; 02 which claims hold up / where evidence is in tension; 03 implications and what to watch.
- **reject** — off-scope, duplicate coverage, no substantive content (teaser, sponsor read, link roundup), or claims with nothing to inspect.
- **defer** — relevant but not yet usable: evidence too thin, waiting for independent confirmation, transcript or text incomplete, or a better fit for a later edition. Say what would change the decision.

Every decision gets a one-to-three-sentence reason that names the specific content, not a generic phrase.

## Changelog

- v1 (2026-10-12): initial policy.
- v2 (2026-10-14): after review of live run 1 — added cost/token usage to relevance; explicit vendor labelling rule (vendor content stays in scope, numbers are source_claims, interest disclosed); accurate description of source expertise; publisher cap of 3; each item serves at most two pieces; piece 02 seeks tension without inventing it; judge media on the whole transcript. Rejected proposal: requiring a non-vendor source before any vendor efficiency claim could be used (too strict for this audience).
