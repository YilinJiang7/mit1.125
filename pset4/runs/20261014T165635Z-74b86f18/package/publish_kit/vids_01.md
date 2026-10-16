# Production sheet: What Changed This Month: Voice-Driven Development, New Models, and Project-Aware Agents

As of 2026-10-14. Target: 3–5 minutes; calm explainer; about 145 spoken words per minute.

## Help me create

Create a 3–5 minute explainer about “What Changed This Month: Voice-Driven Development, New Models, and Project-Aware Agents” for people learning to program who use AI coding agents. Use a calm, clear, practical tone, simple diagrams, readable captions, and no hype. Follow the scene list below and use the supplied narration exactly, without adding facts or rewriting it. Keep source credits and media timestamps visible. Preserve the qualifications about historical data, expert experience, vendor interests, and preprint results wherever they appear. End with the concrete learner action and the article link. Use Google Vids or HeyGen; include the AI voice/visual disclosure in the video description.

## Full narration — copy this one block as the voiceover

```text
This month, AI coding agents took big steps forward. You can now build complex features almost entirely by voice. New large language models, or LLMs, arrived with different prices and speeds. And GitHub Copilot got smarter about understanding your project’s rules. But what does this mean for you, a learner still getting comfortable with programming? What can you safely delegate to your coding agent, and what should you still check yourself? Let’s break it down.

Simon Willison, an expert developer, recently built a new blog feature almost entirely by voice. He used Codex in a local development environment, chatting with his laptop while cooking dinner. Over about 30 minutes, the AI wrote code, asked clarifying questions, and updated multiple files. The feature included new data models, import scripts, and web pages — a multi-step task done mostly by voice.

But Simon also reviewed and fixed the AI’s work afterward. He spent another half hour typing to correct import methods and tweak the display before deploying the feature. So voice-driven coding can handle complex tasks, but it still needs your review and occasional hands-on fixes.

A new model called Gemini 4 Argon launched this month. It’s priced competitively — about $2 per million input tokens and $10 per million output tokens at launch. That’s half or even a fifth of some other top models. But the price will double in December, matching competitors.

What matters most is how many tokens the model uses to complete your task. According to an independent analysis, Gemini 4 Argon is efficient, costing around $2,400 to run a standard benchmark, cheaper than many others. Theo, the video’s creator, reports good front-end coding and 3D results from his own testing, though not perfect. This is one creator’s experience, not an independent evaluation.

So when choosing a model, consider both price per token and total tokens used. This helps balance cost and quality for your projects.

GitHub Copilot now supports project-aware features to better understand your codebase. You can add custom instructions in a file named .github/copilot-instructions.md to tell Copilot your project’s architecture, naming conventions, or testing expectations.

You can also package repeatable procedures as “agent skills” and create “custom agents” for specialized tasks. Plus, MCP servers let Copilot connect to external tools like browsers for testing.

This means you don’t have to explain the same rules every time. Instead, your agent learns your project’s standards and can produce more relevant and correct code. For learners, this reduces repetitive explanations and helps keep agent output consistent.

So what should you do this week? Try this: pick one project convention you often explain to your agent. Add it to .github/copilot-instructions.md. Then see how Copilot applies it on your next coding task.

Remember, you can delegate more complex tasks now — even multi-file features by voice or with project-aware agents. But you still need to review the code carefully, guide the agent with context, and watch your token usage to manage costs.

For full details and references, check out the Apprentice Mode Substack article linked below.
```

## Scene list

Main on-screen text is capped at 12 words; source credits are separate. Follow the approved scene order. Source numbers match the article and YouTube description.

| Scene | On-screen text | Visual suggestion | Source + timestamp to show on screen |
| --- | --- | --- | --- |
| 1 | Delegate more, review carefully, and watch costs. | Three simple panels: voice workflow, model costs, and project instructions. | [1] [A new feature for my blog, built using my voice](https://simonwillison.net/2026/Oct/9/built-using-my-voice) — Simon Willison; published 2026-10-09; written source<br>[2] [llm-gemini 0.35](https://simonwillison.net/2026/Oct/13/llm-gemini) — Simon Willison; published 2026-10-13; written source<br>[3] [GitHub Copilot app for Beginners: How to teach Copilot about your codebase](https://github.blog/ai-and-ml/github-copilot/github-copilot-app-for-beginners-how-to-teach-copilot-about-your-codebase) — GitHub; published 2026-10-12; written source |
| 2 | Expert voice workflow still needs manual review. | Animate the approved workflow: voice instructions → code edits → review → deployment. | [1] [A new feature for my blog, built using my voice](https://simonwillison.net/2026/Oct/9/built-using-my-voice) — Simon Willison; published 2026-10-09; written source |
| 3 | Compare task costs; Theo’s testing is one creator’s experience. | Show token price beside task cost; label Theo’s example as his own testing. | [2] [llm-gemini 0.35](https://simonwillison.net/2026/Oct/13/llm-gemini) — Simon Willison; published 2026-10-13; written source<br>[4] [So I've been testing Gemini 4...](https://www.youtube.com/watch?v=NE006pkiAnk&t=1830) — Theo; 30:30–31:09<br>[5] [So I've been testing Gemini 4...](https://www.youtube.com/watch?v=NE006pkiAnk&t=0) — Theo; 00:00–00:39<br>[6] [So I've been testing Gemini 4...](https://www.youtube.com/watch?v=NE006pkiAnk&t=782) — Theo; 13:02–13:40 |
| 4 | Teach Copilot your project’s rules. | Show a repository diagram with instructions, skills, custom agents, and MCP connections. | [3] [GitHub Copilot app for Beginners: How to teach Copilot about your codebase](https://github.blog/ai-and-ml/github-copilot/github-copilot-app-for-beginners-how-to-teach-copilot-about-your-codebase) — GitHub; published 2026-10-12; written source |
| 5 | Try one project instruction; review results and costs. | Show a test-command instruction being added, followed by a review checklist. | [1] [A new feature for my blog, built using my voice](https://simonwillison.net/2026/Oct/9/built-using-my-voice) — Simon Willison; published 2026-10-09; written source<br>[3] [GitHub Copilot app for Beginners: How to teach Copilot about your codebase](https://github.blog/ai-and-ml/github-copilot/github-copilot-app-for-beginners-how-to-teach-copilot-about-your-codebase) — GitHub; published 2026-10-12; written source |

## Production disclosure

Narration drafted with AI assistance from a source-tracked pipeline; reviewed by the editor, Yilin Jiang. Voice/visuals generated with Google Vids (or HeyGen).

Use ARTICLE_LINK for the final article URL. Review the generated voice and visuals before uploading; retain the supplied narration and source qualifications.
