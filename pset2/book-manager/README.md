# 📚 Book Manager: PSet 2 (MIT 1.125)

A small command-line app for my own reading. It keeps my library, looks up book metadata, tracks a yearly reading goal together with a one-line takeaway per book, and asks **three recommendation agents in parallel** what I should read next. It is built from small Bash programs, with a [Gum](https://github.com/charmbracelet/gum) interface.

**🎬 Demo video:** [VIDEO_LINK](VIDEO_LINK)

---

## How to run

```bash
brew install gum jq          # gum = the interface, jq = reads Open Library's JSON
cd pset2/book-manager
./app.sh                     # start the app
./tests/smoke_test.sh        # optional: 21 offline checks of every component
```

Optional: if the [Codex CLI](https://github.com/openai/codex) is installed and logged in, the three agents ask Codex for their ideas. If Codex is missing, fails, or takes longer than 120 s, each agent falls back to its own offline catalog, so the app always works.

| Setting | Effect |
|---|---|
| `BOOK_AI=offline ./app.sh` | never call Codex |
| `BOOK_THINK_SECONDS=0 ./app.sh` | no simulated "think time" for the offline agents |
| `BOOK_OFFLINE=1 ./app.sh` | no Open Library lookups (the offline catalog is used) |
| `BOOK_SHORTLIST=3`, `BOOK_PER_AGENT=8` | shortlist length, ideas per agent |

---

## Architecture

The app follows **UI → Workflows → Book / Recommendation Components → Data Layer → Storage**, and each responsibility lives in its own small file, so the folder tree already shows the design. `app.sh` only loops: it shows `ui/main_menu.sh` and hands the chosen action to a workflow. The workflows (`manage_library.sh`, `get_recommendations.sh`) decide *what happens in what order*. They call components for the real work and UI screens for all drawing and questions, and they never draw or store anything themselves. `data/book_database.sh` is the only program that reads or writes `books.csv`. Every other file asks it for *pipe records* (`title | author | genre | year | status | rating | finished | takeaway | link`), so no one else knows the storage is CSV, or how quoted commas are handled. All programs talk through plain text on stdin/stdout, which is why they compose with pipes. Recommendations are the clearest example: three independent agents run in the background (`&`, `$!`), a live status line polls them, `wait` synchronises them, and their combined output flows through `cat … | refine_recommendations.sh | tee … | recommendations_screen.sh shortlist`.

```text
                        ┌→ recommend_from_history.sh ───┐
library + interests.txt ├→ recommend_from_interests.sh ─┼→ cat → refine_recommendations.sh → shortlist UI
                        └→ recommend_for_discovery.sh ──┘        clean → drop_owned → merge → rank → cut
```

## What I personalized

The agents reflect how I choose books. **History** builds on what I rated 4–5★ and never lets a single favourite take over the list. **Interests** serves the topics in `data/interests.txt`: AI & agent engineering, data science & statistics, psychology, sociology, history, fiction, and mystery. Every interest gets a turn. **Discovery** deliberately picks from genres I have *never* shelved, such as poetry, nature writing, food, and graphic novels, at most one book per genre. The refiner ranks books that several agents agree on first ("★ 2 agents agree"), and it always keeps at least one idea from each perspective. I added two features I actually wanted. The first is a **yearly reading goal** with a pace check ("3 behind pace"). The second is a **one-sentence takeaway** for every finished book, collected on the goal screen as "what I took away this year". When I mark a book *finished*, the app dates it and asks me for a rating and a takeaway, so the habit is built into the workflow.

---

## Files

| Layer | File | In → Out |
|---|---|---|
| entry | `app.sh` | menu choice → runs the matching workflow, loops |
| UI | `ui/main_menu.sh` | status line → chosen action (`browse`, `add`, …) on stdout |
| UI | `ui/library_screen.sh` | records on stdin → table / card / goal bar; Gum prompts → answer on stdout |
| UI | `ui/recommendations_screen.sh` | agent states → live progress line; shortlist on stdin → cards / choice |
| UI | `ui/theme.sh` *(added)* | colours + tiny helpers shared by the screens (spinner, stars, pause) |
| workflow | `workflows/manage_library.sh` | `browse · add · search · update · goal · summary` |
| workflow | `workflows/get_recommendations.sh` | parallel agents → progress → wait → combine → refine → UI → save |
| book | `books/fetch_book_metadata.sh` | `Dune \| Frank Herbert` → `Dune \| Frank Herbert \| Science Fiction \| 1965 \| link` |
| book | `books/search_books.sh` | term (argument or stdin), e.g. `history`, `status:reading`, `rating:4` → matching records |
| agent | `recommendations/recommend_from_history.sh` | liked books → `Title \| Author \| Genre \| Reason \| history` |
| agent | `recommendations/recommend_from_interests.sh` | interests.txt → `… \| interests` |
| agent | `recommendations/recommend_for_discovery.sh` | comfort zone → `… \| discovery` |
| agent | `recommendations/ask_codex.sh` *(added)* | prompt → validated 4-field lines, or exit 1 (the agent then uses its offline logic) |
| filter | `recommendations/refine_recommendations.sh` | candidates on stdin → ≤ 5 clean lines on stdout |
| data | `data/book_database.sh` | `list · search · get · exists · add · update · update-status · update-rating · interests · catalog · genres · goal · set-goal` |
| storage | `data/books.csv`, `interests.txt`, `catalog.txt`, `settings.txt` | touched only by `book_database.sh` |
| test | `tests/smoke_test.sh` *(added)* | 21 checks, run on a temporary copy of the data |

The three added files each have one clear job, and the required layers are all kept.

## Where each required concept lives

| Concept | Where |
|---|---|
| Small Bash programs | 16 scripts, 20–140 lines each, one responsibility per file |
| Pipes | `cat … \| refine_recommendations.sh \| tee … \| recommendations_screen.sh shortlist`; refinement is itself `clean \| drop_owned \| merge_duplicates \| rank \| shortlist`; `echo "$term" \| search_books.sh`; `echo "$record" \| book_database.sh add` |
| Parallelization | `get_recommendations.sh` step 1: `… &` and `PIDS[$i]=$!`, then `wait "${PIDS[$i]}"` |
| Streaming / progress | the live line `⠹ 2s ✔ history 1s ● interests… ● discovery…`, redrawn with `\r`; per-agent timings; "total 3s in parallel · one after another ~6s"; Gum spinners during metadata lookups |
| Gum | `gum choose` (menu, status, rating), `gum filter` (pick a book), `gum input`, `gum confirm`, `gum spin`, `gum style` (cards, banner) |
| Codex | `ask_codex.sh` runs `codex exec` behind a watchdog timeout; each agent sends a different prompt that matches its way of thinking |
| Data-layer boundary | `tests/smoke_test.sh` checks that no other file mentions `books.csv` |

## Tracing one workflow: "Get recommendations"

1. `app.sh` → `ui/main_menu.sh` prints `recommend` → `app.sh` runs `workflows/get_recommendations.sh`.
2. The workflow starts the three agents with `&`, keeping each `$!`. Every agent writes to its own file in a temp folder, so the agents never share an output.
3. Each agent reads what it needs **through the data layer** (`book_database.sh list`, `interests`, `catalog`), then asks Codex via `ask_codex.sh` or falls back to its offline rule. It prints `Title | Author | Genre | Reason | source`.
4. While the agents run, the workflow polls `kill -0 PID` every 0.2 s and calls `recommendations_screen.sh progress`, which redraws one status line.
5. `wait` on each PID is the synchronisation point: after it, all three files are complete.
6. `cat` joins the three files and pipes them into `refine_recommendations.sh`. The refiner drops malformed lines, drops books I already own (`book_database.sh exists`), merges duplicates into `history+interests`, ranks consensus first and then alternates between agents, and finally keeps 5 books with every agent represented.
7. `tee` saves a copy while `recommendations_screen.sh shortlist` draws the cards. `pick` lets me choose one book.
8. The workflow reuses `fetch_book_metadata.sh` for the year and link, then pipes the new record into `book_database.sh add` with the status `want-to-read`.

## Honest notes

- The offline agents sleep 1–3 s on purpose ("think time"), so the parallel progress line can be seen in a demo. With Codex the waiting is real. `BOOK_THINK_SECONDS=0` turns the delay off.
- `data/catalog.txt` is a hand-picked list of 80 books. It is the agents' knowledge when there is no AI, and a local fallback for metadata.
- The code is written for macOS's default Bash 3.2 and BSD tools: no associative arrays, no `sed -i`, no GNU-only flags.
