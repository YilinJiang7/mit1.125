# Production sheet: How Learners Should Work with Coding Agents Now: Guide to Delegation, Review, and Cost Management

As of 2026-10-14. Target: 3–5 minutes; calm explainer; about 145 spoken words per minute.

## Help me create

Create a 3–5 minute explainer about “How Learners Should Work with Coding Agents Now: Guide to Delegation, Review, and Cost Management” for people learning to program who use AI coding agents. Use a calm, clear, practical tone, simple diagrams, readable captions, and no hype. Follow the scene list below and use the supplied narration exactly, without adding facts or rewriting it. Keep source credits and media timestamps visible. Preserve the qualifications about historical data, expert experience, vendor interests, and preprint results wherever they appear. End with the concrete learner action and the article link. Use Google Vids or HeyGen; include the AI voice/visual disclosure in the video description.

## Full narration — copy this one block as the voiceover

```text
Are AI coding agents like Codex, Claude Code, or GitHub Copilot ready to do your programming homework for you? As these tools get smarter and more autonomous, what should you, as a learner, delegate to them — and what must you still do yourself? Today, we’ll explore how to work effectively with these agents, what risks to watch out for, and how to manage costs. Let’s get started.

First, it helps to give your coding agent explicit instructions about your project. According to GitHub’s Copilot team, you can add a file called .github/copilot-instructions.md to your repository. This file tells Copilot your project’s conventions, like naming styles or testing expectations. This way, the agent doesn’t have to relearn your rules every time and can produce more relevant code.

Start small: pick one convention you often explain, add it to that file, and see how Copilot applies it next time. This reduces repetitive explanations and helps the agent work more smoothly with your codebase.

But don’t trust the agent blindly. A big risk is what experts call the “silent green exit.” According to a Stack Overflow blog post, AI agents can report success — like an exit code zero or passing tests — even when they actually did nothing or produced empty results. This is because the success signal is often just the agent saying “I’m done,” without any real verification.

So, as a learner, you must carefully review the code and outputs yourself. Don’t rely only on green lights or passing tests. Look at the actual code, run your own tests, and watch for subtle errors or missing functionality.

Another practical concern is cost. AI models charge per token — that means every piece of text you send or receive costs money. New models vary a lot in price and efficiency. For example, Google’s Gemini 4 Argon model launched at $2 per million input tokens and $10 per million output tokens, which is cheaper than some competitors.

But price per token isn’t the whole story. Some cheaper models use many more tokens to complete a task, making them more expensive overall. So, learners should pick models that balance cost and token efficiency for their specific tasks.

HiSentinel is a non-peer-reviewed arXiv preprint describing intervention sentinels that allow, pause, or redirect an agent before execution. The authors report task completion improvements of up to 14% on their own benchmarks.

This is research worth watching, not a tool learners can adopt from these results. The benchmarks do not establish benefits for learners, so keep that limit in mind when following intervention research.

Thariq Shihipar, an Anthropic employee describing Anthropic’s own product Claude Code, recommends specifying effort and verification priorities, such as edge cases or security checks. This advice has a commercial interest; it is not an independent evaluation.

Thariq says this guidance helps avoid costly prompting loops and rate limits. He compares advanced prompting to advanced executive communication: giving your agent a clear memo about priorities.

Looking ahead, learners should watch for advances in agent autonomy and operability. According to Stack Overflow’s production-grade agent guide, mature systems include features like observability, cost control, model routing, fallback options, and kill switches.

These features help you understand what your agent is doing, control spending, and safely stop or override actions. As agents become more autonomous, these controls will be essential for safe and efficient delegation.

This week, try adding a .github/copilot-instructions.md file to your current project. Pick one coding convention or testing expectation you often explain, write it down there, and see how your coding agent adapts. Remember, always review the agent’s output carefully, and keep an eye on your token usage.

For full references and deeper reading, check out the Apprentice Mode Substack article linked below.
```

## Scene list

Main on-screen text is capped at 12 words; source credits are separate. Follow the approved scene order. Source numbers match the article and YouTube description.

| Scene | On-screen text | Visual suggestion | Source + timestamp to show on screen |
| --- | --- | --- | --- |
| 1 | Delegate with context, review, and cost awareness. | Introduce a learner, a code editor, and a simple review checklist. | [1] [GitHub Copilot app for Beginners: How to teach Copilot about your codebase](https://github.blog/ai-and-ml/github-copilot/github-copilot-app-for-beginners-how-to-teach-copilot-about-your-codebase) — GitHub; published 2026-10-12; written source<br>[2] [A new feature for my blog, built using my voice](https://simonwillison.net/2026/Oct/9/built-using-my-voice) — Simon Willison; published 2026-10-09; written source |
| 2 | Give agents your project’s conventions. | Show one naming or test convention in the repository instructions file. | [1] [GitHub Copilot app for Beginners: How to teach Copilot about your codebase](https://github.blog/ai-and-ml/github-copilot/github-copilot-app-for-beginners-how-to-teach-copilot-about-your-codebase) — GitHub; published 2026-10-12; written source |
| 3 | Verify actual outputs beyond a green check. | Contrast a success signal with inspection of code and test results. | [3] [A green exit code is not evidence that the work happened](https://stackoverflow.blog/2026/10/08/a-green-exit-code-is-not-evidence-that-the-work-happened) — Stack Overflow; published 2026-10-08; written source |
| 4 | Balance token price with tokens used per task. | Show separate token-price and task-usage columns; use only figures in the voiceover. | [4] [llm-gemini 0.35](https://simonwillison.net/2026/Oct/13/llm-gemini) — Simon Willison; published 2026-10-13; written source<br>[5] [I thought AI was gonna get cheaper?](https://www.youtube.com/watch?v=vRS2leJLAI0&t=738) — Theo; 12:18–12:56 |
| 5 | HiSentinel: preprint results worth watching, not adopting. | Animate allow, redirect, and pause; display the non-peer-reviewed benchmark qualification. | [6] [Learning When and How to Intervene: A Hindsight-Distilled Sentinel for Coding Agents](https://arxiv.org/abs/2609.39957v1) — arXiv; published 2026-09-30; written source |
| 6 | Anthropic employee’s Claude Code advice has a commercial interest. | Show an effort-and-verification memo with a vendor-advice label. | [7] [Claude Code’s Next Era — Thariq Shihipar, Anthropic](https://www.latent.space/p/thariq) — Latent Space; 21:52–23:43<br>[8] [Claude Code’s Next Era — Thariq Shihipar, Anthropic](https://www.latent.space/p/thariq) — Latent Space; 29:44–30:31 |
| 7 | Watch observability, cost controls, routing, and kill switches. | Show four labelled controls around an agent workflow. | [9] [Production-grade LLMs and agents: a field guide](https://stackoverflow.blog/2026/10/08/production-grade-llms-and-agents-a-field-guide) — Stack Overflow; published 2026-10-08; written source<br>[10] [Claude Code’s Next Era — Thariq Shihipar, Anthropic](https://www.latent.space/p/thariq) — Latent Space; 14:31–15:14 |
| 8 | Add one instruction; review outputs and token usage. | Show a single project instruction, a review checkbox, and an article-link end card. | [1] [GitHub Copilot app for Beginners: How to teach Copilot about your codebase](https://github.blog/ai-and-ml/github-copilot/github-copilot-app-for-beginners-how-to-teach-copilot-about-your-codebase) — GitHub; published 2026-10-12; written source |

## Production disclosure

Narration drafted with AI assistance from a source-tracked pipeline; reviewed by the editor, Yilin Jiang. Voice/visuals generated with Google Vids (or HeyGen).

Use ARTICLE_LINK for the final article URL. Review the generated voice and visuals before uploading; retain the supplied narration and source qualifications.
