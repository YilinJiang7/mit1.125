# 📚 Book Manager — PSet 2 (MIT 1.125)

A small personal book manager for the terminal, built from small Bash programs with a [Gum](https://github.com/charmbracelet/gum) interface. It keeps my library, looks up book metadata, searches my books, and asks three recommendation agents, running in parallel, what I should read next.

**🎬 Demo video:** [watch on YouTube](https://youtu.be/w0VZXkEsENc) · or the 480p copy in this folder: [mit1.125-pset2-YilinJiang.mov](mit1.125-pset2-YilinJiang.mov)

## How to run

```bash
brew install gum jq        # Gum draws the interface; jq reads Open Library's JSON
cd pset2/book-manager
./app.sh
```

The three recommendation agents ask the [Codex CLI](https://github.com/openai/codex) for ideas if it is installed and logged in, which can take a little while. Without Codex (or with `BOOK_AI=offline ./app.sh`) they fall back to a small offline catalog, with a short simulated delay so the parallel progress is visible.

## Architecture

The app follows the required layering, **UI → Workflows → Book / Recommendation Components → Data Layer → Storage**, with one responsibility per file and calls that only go downward. `app.sh` checks for Gum and starts `ui/main_menu.sh`. The UI screens (`ui/`) are the only files that ask the user anything or draw anything, and they hand every request to a workflow. The workflows (`workflows/`) decide what happens in what order: `manage_library.sh` runs User Input → Metadata → Database for adding a book and Search Request → Search Component → Results for searching; `get_recommendations.sh` starts the three agents in the background with `&`, keeps each PID from `$!`, polls them and streams a progress line while they run, synchronises with `wait`, then combines their outputs with `cat` and pipes them into `refine_recommendations.sh`, which removes duplicates and books I already own and keeps a short list for the UI. The components (`books/`, `recommendations/`) do the actual work, and `data/book_database.sh` is the only program that reads or writes `books.csv`; everyone else asks it for one-line records (`title | author | genre | …`), so the rest of the app does not care how the data is stored. I added three small helper files: `ui/theme.sh` (shared colours and helpers for the screens), `recommendations/ask_codex.sh` (the shared Codex call with a timeout) and `tests/smoke_test.sh` (quick self-checks).

```text
                        ┌→ recommend_from_history.sh ───┐
library + interests.txt ├→ recommend_from_interests.sh ─┼→ cat → refine_recommendations.sh → UI
                        └→ recommend_for_discovery.sh ──┘
```

## What I personalized

The three agents reflect how I pick books. **History** builds on the books I rated 4–5★, taking turns between them so one favourite cannot fill the list. **Interests** serves the topics in `data/interests.txt` — AI and agent engineering, data science and statistics, psychology, sociology, history, fiction, and mystery — giving each interest a turn. **Discovery** deliberately suggests genres I have never shelved, one book per genre, so I step outside my usual reading. When two agents suggest the same book, the refiner ranks it first. I also added two things I actually wanted: a **yearly reading goal** with a pace check, and a **one-sentence takeaway** for every finished book; when I mark a book finished, the app dates it and asks for a rating and a takeaway.
