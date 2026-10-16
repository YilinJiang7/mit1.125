# Run 1 editorial review

Run: `runs/20261013T035421Z-98ff50c1` (as-of 2026-10-13, policy v1, model gpt-4.1-mini)
Prepared 2026-10-13 by Claude (assistant) as a starting point; reviewed and decided by Yilin Jiang on 2026-10-14. The last column records Yilin's own judgment.

## A. Sample of decisions (3 accepted + 4 rejected/deferred)

| # | Item | AI decision | AI's reason (short) | Claude's suggested judgment | Yilin's judgment |
|---|---|---|---|---|---|
| 1 | Simon Willison, "A new feature for my blog, built using my voice" (feed, 2026-10-09) `feed:19c45cc3…` | accept → 01, 03 | First-hand Codex voice-mode workflow; calls him a "learner-level programmer" | **Agree with accept, reason contains a factual error.** Simon Willison is a very experienced developer (co-creator of Django), not a learner. The workflow is still useful, but it shows what an *expert* can delegate, which is a limit on how far it transfers to beginners. → human correction C1. || Agree: accept is right, but the AI's reason is factually wrong about the author's experience. Correction C1. |
| 2 | GitHub Blog, "ReviewBench: An open benchmark for AI code review" (feed, 2026-10-05) `feed:e4f96ea3…` | accept → 01 | Rigorous benchmark that helps learners understand AI reviewers | **Disagree — should be defer (or reject).** It is a vendor benchmark for team code-review agents; its "trustworthy, anticipates production improvements" claim is GitHub's own claim about its own tooling (commercial incentive). A learner can't act on it this week. Also: 6 of 14 accepts came from GitHub → vendor skew. || Agree with Claude: defer. Vendor benchmark for team code-review tools; not actionable for a learner this week. |
| 3 | Stack Overflow Blog, "A green exit code is not evidence that the work happened" (feed, 2026-10-08) `feed:2e5589be…` | accept → 01, 02, 03 | Silent-failure mode; agents report success without doing the work | **Agree.** Strongest learner-relevant item in the run. But some evidence it cites (trust survey) is from 2024–25: the brief must say what is *newly* reported here vs. older data (policy §2). || Agree: accept. Must separate the newly reported part from the older 2024–25 survey data. |
| 4 | Changelog, "From zero to NanoClaw (Interview)" (podcast, 2026-10-09) `podcast:cc5b25ae…` | reject | "Mostly an interview introduction and sponsor pitch" | **Disagree — AI only saw the opening.** The excerpt was the first ~6k characters (intro + sponsor reads). The 45-min transcript mentions "agent" 67 times; the guest builds an agent project and argues agents can rewrite codebases. Should be at least defer, likely accept for 02 (a strong, testable claim). Cause = code (excerpt), not policy. || Agree: the reject came from the excerpt bug (AI only saw the intro). Should be at least defer, likely accept for piece 02. |
| 5 | Latent Space, "Claude Code's Next Era — Thariq Shihipar, Anthropic" (podcast, 2026-09-29) `podcast:8c47bc8f…` | defer | Informal conversation, lacks concrete workflows | **Disagree — should be accept (01/03), labelled vendor.** An Anthropic Claude Code team member on how agentic coding is changing and what skills users need (e.g. seg-0020 ~15:00 on prompting as a "meta skill"). Vendor incentive must be flagged, but it is first-hand and directly on topic. Same excerpt problem as #4. || Agree: accept. A vendor employee talking about their own product is usable first-hand evidence **as long as the commercial interest is stated explicitly**. |
| 6 | Theo, "I thought AI was gonna get cheaper?" (YouTube, 2026-10-12) `youtube:vRS2leJLAI0` | defer | Transcript interrupted by sponsor; not focused on learners | **Partly disagree — accept for 03.** Cost per task is a real constraint for students on limited budgets; the claim (price per token up, cost per task maybe down) is exactly the kind of claim piece 02 should test. Practitioner commentary, not data → source_claim. || Agree: accept for 03. Cost and token usage are exactly what beginners don't have a feel for and want to understand (see policy v2 §1). |
| 7 | Simon Willison, "Dwarf Fortress uses version control now" (feed, 2026-10-11) `feed:e179bee0…` | reject | Not about coding agents | **Agree.** Correct, specific reason. (Shows the AI also gets easy cases right.) || Agree: correct reject. |

## B. Factual corrections and classification errors found in run 1 briefs/articles

| ID | Where | Problem | Correction |
|---|---|---|---|
| C1 | decision #1 reason; any draft that calls Simon Willison a learner | Wrong description of the source | Describe him as an experienced developer; frame the workflow as "what an expert can delegate" |
| C2 | Brief 03 claim `03-c2` ("improving productivity") typed `reported_fact` | Vendor productivity claim, no independent evidence | Re-type as `source_claim`, attribute to GitHub |
| C3 | Brief 01 claim `01-c5` (inference "reducing manual implementation time") | Not supported by any cited evidence | Remove or rewrite as an open question |
| C4 | Brief 02 claim `02-c2` (developer trust declined) | Older survey data presented as this month's news | Say it is 2024–25 survey data cited in a recent article |
| C5 | Run 1 decisions | Theo labelled "vendor" | He is a developer/influencer (with his own products) → "practitioner", note the attention incentive |
| C6 | All three articles, "Sources" sections | Same source listed up to 5 times; articles 1,072–1,169 words (target 600–900) | Code fix: dedupe sources; enforce length |

## C. What these problems tell us (feeds policy v2)

1. **Vendor skew**: 6/14 accepts from GitHub; pieces 01 and 03 overlap (canvases, Simon's voice demo appear in both).
2. **Piece 02 has no real tension**: all its sources agree; no claim is actually tested against counter-evidence.
3. **Media judged on intros only** (code bug) → podcasts and videos systematically under-accepted.
4. **Claim typing too generous**: vendor statements labelled `reported_fact`.

Policy v2 changes — decided by Yilin on 2026-10-14 (implemented in `config/editorial_policy.md` v2):

- Max **3 accepted items per publisher** per run; when over the cap, keep the ones closest to original evidence and defer the rest with reason "publisher cap". (Yilin: 3 is fine; a strong publisher can still be represented by its 3 best items.)
- ~~A vendor item is accepted only if (a) it announces a change a learner can use now, or (b) it is paired with a non-vendor source testing the same claim.~~ **Yilin rejected this as too strict**: efficiency, speed, cost and token usage are among the things beginners care about most and understand least, so they stay in scope. Final rule: vendor items on these topics can be accepted; their numbers are always typed `source_claim`, attributed to the vendor, and the commercial interest is stated; an independent source is paired with them *when one exists*, otherwise the article says the claim is unverified. Cost/token usage for a student is added explicitly to audience relevance.
- Piece 02 looks for at least one claim where two sources disagree or measure different things; if none exists, it says so explicitly rather than inventing tension. (Yilin checked: the README asks piece 02 "where are the evidence or interpretations in tension?" and says "Do not manufacture disagreement when the evidence does not support it" — so tension is sought, not required.)
- Each accepted item should normally serve **one** piece (two at most) so the three pieces stay distinct.
- Describe the source's expertise accurately (expert vs. learner) when judging transferability to beginners.

## D. Approval of run 1

Run 1 is the **baseline**. Do not publish it; publish from run 2 (policy v2). Yilin's decision: **revise** (baseline only). Recorded as a `revise` decision in `runs/20261013T035421Z-98ff50c1/approval.json` with notes pointing here.


## E. Corrections status

Yilin agreed with corrections C1–C6 on 2026-10-14. C6 was fixed in code (commit 7b89003). C1–C5 are addressed by policy v2 and verified in run 2's decisions/briefs before approval.

### Status after policy v2

Run 2 (`runs/20261014T165635Z-74b86f18`, as-of 2026-10-14) uses policy v2. The publisher cap and whole-transcript sampling improvements are in place, but policy changes alone did not resolve every attribution and evidence-scope problem. Yilin supplied human corrections R1–R7: attribute Claude Code advice to an Anthropic employee discussing Anthropic’s own product with a commercial interest; date the trust figures to the 2024 and 2025 Stack Overflow Developer Surveys cited in the Oct 8, 2026 article; distinguish Theo’s own testing from an independent evaluation; qualify HiSentinel as a non-peer-reviewed arXiv preprint tested on the authors’ benchmarks and worth watching rather than adopting; trim article 03; remove article 01’s stray limitation markers; and update all six editorial disclosures. Exact before/after text and reasons are recorded in [the run 2 human review](run2_editorial_review.md).

Two AI-versus-human disagreements remain after policy v2:

| Item | Saved run 2 AI decision | Yilin’s judgment | Status after policy v2 |
| --- | --- | --- | --- |
| `feed:e4f96ea3e7c3ac5d94a4995fb08371a2c7f7b6af` — ReviewBench | accept, proposed piece 01 | defer: vendor benchmark for team code-review tools; not actionable for a learner this week | Still accepted by the AI, but not used in any brief, article or script. Decision retained unchanged; no draft correction needed. |
| `podcast:cc5b25aebfd7bdb8a79516843a8f804db441154c` — NanoClaw | reject | would accept/defer: the agent-project and agent-driven code-rewriting discussion is relevant and deserves examination | Whole-transcript sampling did not remove the editorial disagreement: the AI still rejected it as business/security-focused and insufficiently actionable. Not used in any piece; decision retained unchanged. |

Run 1’s generated artifacts and its baseline-only `revise` decision remain unchanged. Run 2’s corrections are human edits; collection, selection, brief generation and content generation are not rerun.
