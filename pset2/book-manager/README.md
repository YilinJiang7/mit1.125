# 📚 Book Manager: PSet 2 (MIT 1.125)

A small command-line app for my own reading. It keeps my library, looks up book metadata, tracks a yearly reading goal together with a one-line takeaway per book, and asks **three recommendation agents in parallel** what I should read next. It is built from small Bash programs, with a [Gum](https://github.com/charmbracelet/gum) interface.

**🎬 Demo video:** [VIDEO_LINK](VIDEO_LINK)

---

## How to run

```bash
brew install gum jq          # gum = the interface, jq = reads Open Library's JSON
cd pset2/book-manager
./app.sh                     # start the app
./tests/smoke_test.sh        # optional: 29 offline checks, incl. the layering rules
```

Optional: if the [Codex CLI](https://github.com/openai/codex) is installed and logged in, the three agents ask Codex for their ideas. If Codex is missing, fails, or takes longer than 120 s, each agent falls back to its own offline catalog, so the app always works.

| Setting | Effect |
|---|---|
| `BOOK_AI=offline ./app.sh` | never call Codex |
| `BOOK_THINK_SECONDS=0 ./app.sh` | no simulated "think time" for the offline agents |
| `BOOK_OFFLINE=1 ./app.sh` | no Open Library lookups (the offline catalog is used) |
| `BOOK_SHORTLIST=3`, `BOOK_PER_AGENT=8` | shortlist length, ideas per agent |

### Every component also runs on its own

```bash
./data/book_database.sh search "kahneman"                 # the data layer, directly
./books/search_books.sh "history"                         # search by argument…
echo "status:reading" | ./books/search_books.sh           # …or through a pipe
./books/fetch_book_metadata.sh "Dune | Frank Herbert"     # one line in, one enriched line out
./recommendations/recommend_for_discovery.sh              # one agent alone
./workflows/manage_library.sh search "rating:5"         # a workflow, without the UI
./workflows/get_recommendations.sh | cut -d'|' -f1       # the whole parallel workflow as one pipe stage
```

---

## Architecture

The app follows **UI → Workflows → Book / Recommendation Components → Data Layer → Storage**, and every call goes strictly downward, never up and never skipping a layer. Each responsibility lives in its own small file, so the folder tree already shows the design. `app.sh` checks for Gum and starts `ui/main_menu.sh`. The UI screens are the only files that ask the user anything or draw anything; they hand every request to a workflow. The workflows (`manage_library.sh`, `get_recommendations.sh`) are **headless**: arguments or stdin go in, pipe records come out on stdout, and they decide *what happens in what order* by calling the components. `data/book_database.sh` is the only program that reads or writes `books.csv`. Every other file asks it for *pipe records* (`title | author | genre | year | status | rating | finished | takeaway | link`), so no one else knows the storage is CSV, or how quoted commas are handled. Because everything talks in plain text, the layers compose with pipes. Recommendations are the clearest example: the workflow runs three independent agents in the background (`&`, `$!`), polls them, synchronises them with `wait`, and pipes their combined output through `refine_recommendations.sh` to stdout. While it works, it streams progress events on stderr; `recommendations_screen.sh` runs it as `get_recommendations.sh --progress 2>&1 >shortlist | draw_progress`, drawing the events live and the shortlist at the end. `tests/smoke_test.sh` checks the layering rules automatically.

```text
                        ┌→ recommend_from_history.sh ───┐
library + interests.txt ├→ recommend_from_interests.sh ─┼→ cat → refine_recommendations.sh → stdout → UI
                        └→ recommend_for_discovery.sh ──┘        clean → drop_owned → merge → rank → cut
```

## What I personalized

The agents reflect how I choose books. **History** builds on what I rated 4–5★ and never lets a single favourite take over the list. **Interests** serves the topics in `data/interests.txt`: AI & agent engineering, data science & statistics, psychology, sociology, history, fiction, and mystery. Every interest gets a turn. **Discovery** deliberately picks from genres I have *never* shelved, such as poetry, nature writing, food, and graphic novels, at most one book per genre. The refiner ranks books that several agents agree on first ("★ 2 agents agree"), and it always keeps at least one idea from each perspective. I added two features I actually wanted. The first is a **yearly reading goal** with a pace check ("3 behind pace"). The second is a **one-sentence takeaway** for every finished book, collected on the goal screen as "what I took away this year". When I mark a book *finished*, the app dates it and asks me for a rating and a takeaway, so the habit is built into the workflow.

---

## Files

| Layer | File | In → Out |
|---|---|---|
| entry | `app.sh` | checks for Gum → starts the main menu |
| UI | `ui/main_menu.sh` | menu loop: status line from the library workflow → Gum choice → opens a screen |
| UI | `ui/library_screen.sh` | `browse · add · search · update · goal` screens: Gum prompts → library workflow → table / card / goal bar |
| UI | `ui/recommendations_screen.sh` | `show`: runs the recommendation workflow, draws its progress events live, then the shortlist; saves a pick through the library workflow |
| UI | `ui/theme.sh` *(added)* | colours + tiny helpers shared by the screens (spinner, stars, pause) |
| workflow | `workflows/manage_library.sh` | headless: `list · search · details · prepare · save · save-recommendation · update · goal-status · finished-this-year · set-goal · summary` |
| workflow | `workflows/get_recommendations.sh` | headless: parallel agents → wait → combine → refine → shortlist on stdout (`--progress` adds events on stderr) |
| book | `books/fetch_book_metadata.sh` | `Dune \| Frank Herbert` → `Dune \| Frank Herbert \| Science Fiction \| 1965 \| link` |
| book | `books/search_books.sh` | term (argument or stdin), e.g. `history`, `status:reading`, `rating:4` → matching records |
| agent | `recommendations/recommend_from_history.sh` | liked books → `Title \| Author \| Genre \| Reason \| history` |
| agent | `recommendations/recommend_from_interests.sh` | interests.txt → `… \| interests` |
| agent | `recommendations/recommend_for_discovery.sh` | comfort zone → `… \| discovery` |
| agent | `recommendations/ask_codex.sh` *(added)* | prompt → validated 4-field lines, or exit 1 (the agent then uses its offline logic) |
| filter | `recommendations/refine_recommendations.sh` | candidates on stdin → ≤ 5 clean lines on stdout |
| data | `data/book_database.sh` | `list · search · get · exists · add · update · update-status · update-rating · interests · catalog · genres · goal · set-goal` |
| storage | `data/books.csv`, `interests.txt`, `catalog.txt`, `settings.txt` | touched only by `book_database.sh` |
| test | `tests/smoke_test.sh` *(added)* | 29 checks on a temporary copy of the data, including the top-down layering rules |

The three added files each have one clear job, and the required layers are all kept.

## Where each required concept lives

| Concept | Where |
|---|---|
| Small Bash programs | 16 scripts, 20–140 lines each, one responsibility per file |
| Pipes | `cat … \| refine_recommendations.sh` inside the workflow; `get_recommendations.sh --progress 2>&1 >shortlist \| draw_progress` in the UI (progress streamed through a pipe); `get_recommendations.sh \| cut -d'\|' -f1` (the whole workflow as a pipe stage); refinement is itself `clean \| drop_owned \| merge_duplicates \| rank \| shortlist`; `echo "$term" \| search_books.sh`; `echo "$record" \| book_database.sh add` |
| Parallelization | `get_recommendations.sh` step 1: `… &` and `PIDS[$i]=$!`, then `wait "${PIDS[$i]}"` |
| Streaming / progress | the workflow streams events (`tick 7 2 history=done:2s interests=running …`) on stderr; the UI reads them line by line and redraws one live line `⠹ 2s ✔ history 2s ● interests… ● discovery…` with `\r`; per-agent timings; "total 4s in parallel · one after another ~9s"; Gum spinners during metadata lookups |
| Gum | `gum choose` (menu, status, rating), `gum filter` (pick a book), `gum input`, `gum confirm`, `gum spin`, `gum style` (cards, banner) |
| Codex | `ask_codex.sh` runs `codex exec` behind a watchdog timeout; each agent sends a different prompt that matches its way of thinking |
| Layer boundaries | `tests/smoke_test.sh` checks that only the data layer mentions `books.csv`, the UI never skips the workflows, workflows never call the UI, components never call upward, and the data layer calls nothing |

## Tracing one workflow: "Get recommendations"

1. `app.sh` → `ui/main_menu.sh` → I choose *Get recommendations* → `ui/recommendations_screen.sh show`.
2. The screen runs `workflows/get_recommendations.sh --progress 2>&1 >shortlist | draw_progress`: the workflow's stderr (progress events) goes into the pipe, its stdout (the result) into a temp file.
3. The workflow starts the three agents with `&`, keeping each `$!`. Every agent writes to its own file in a temp folder, so the agents never share an output.
4. Each agent reads what it needs **through the data layer** (`book_database.sh list`, `interests`, `catalog`), then asks Codex via `ask_codex.sh` or falls back to its offline rule. It prints `Title | Author | Genre | Reason | source`.
5. While the agents run, the workflow polls `kill -0 PID` every 0.2 s and emits a `tick …` event; the screen redraws one status line for each event.
6. `wait` on each PID is the synchronisation point: after it, all three files are complete, and an `agent …` event per agent reports ideas and time.
7. `cat` joins the three files and pipes them into `refine_recommendations.sh`. The refiner drops malformed lines, drops books I already own (`book_database.sh exists`), merges duplicates into `history+interests`, ranks consensus first and then alternates between agents, and keeps 5 books with every agent represented. That shortlist is the workflow's stdout.
8. The screen draws the shortlist as cards and lets me pick one with Gum. It hands the pick to `manage_library.sh save-recommendation`, which reuses `fetch_book_metadata.sh` for the year and link and pipes the new record into `book_database.sh add` as `want-to-read`.

## Honest notes

- The offline agents sleep 2, 3 and 4 s on purpose ("think time"), so the demo shows them finishing one by one while the total stays at about 4 s instead of 9 s. With Codex the waiting is real. `BOOK_THINK_SECONDS=0` turns the delay off.
- `data/catalog.txt` is a hand-picked list of 80 books. It is the agents' knowledge when there is no AI, and a local fallback for metadata.
- The code is written for macOS's default Bash 3.2 and BSD tools: no associative arrays, no `sed -i`, no GNU-only flags.
