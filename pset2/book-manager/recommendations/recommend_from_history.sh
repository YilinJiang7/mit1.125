#!/bin/bash
# Recommendation agent: recommend from reading history and saved books.
#
# Way of thinking: "You loved X, so here is something like X."
#   input:  finished / highly rated books, read through the data layer
#   output: candidate lines on stdout ->  Title | Author | Genre | Reason | history
#   stderr: one line saying which brain was used (codex or offline catalog)
# Independent of the other agents, so get_recommendations.sh can run it in parallel.

HERE="$(cd "$(dirname "$0")" && pwd)"
DB="$HERE/../data/book_database.sh"
N="${BOOK_PER_AGENT:-6}"

# Books that say something about taste: finished, or rated 4-5. Best-rated first.
liked=$("$DB" list | awk -F'|' '
  function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
  { status = trim($5); rating = trim($6) }
  status == "finished" || rating + 0 >= 4 { print trim($1) "|" trim($2) "|" trim($3) "|" rating }' |
  sort -t'|' -k4,4nr)

if [ -z "$liked" ]; then
  echo "history agent: no finished or rated books yet" >&2
  exit 0
fi

prompt="You are a book recommendation agent that works ONLY from the reader's history.
Books the reader finished, as title|author|genre|rating (1-5, empty = unrated):
$liked

Recommend $N books that build directly on the highest-rated ones. Never repeat a listed book.
Reply with exactly $N lines and nothing else, each in this format:
Title | Author | Genre | Reason
Genre must be one of: $("$DB" genres | tr '\n' ',' | sed 's/,$//').
Reason: at most 12 words, and name the book it builds on."

if ideas=$("$HERE/ask_codex.sh" "$prompt"); then
  echo "history agent: codex" >&2
  echo "$ideas" | head -n "$N" | sed 's/$/ | history/'
  exit 0
fi

echo "history agent: offline catalog" >&2
sleep "${BOOK_THINK_SECONDS:-2}"   # simulated think time (2/3/4 s per agent), so the progress line
                                   # shows the agents finishing one by one

# Offline: walk the liked books best-first, and for each one take the next catalog
# book of the same genre. Round-robin, so one favourite cannot fill the whole list.
{ echo "$liked" | sed 's/^/L|/'
  "$DB" catalog | awk -v seed="$RANDOM" 'BEGIN { srand(seed) } { print rand() "\t" $0 }' | sort -n | cut -f2- | sed 's/^/C|/'
} | awk -F'|' -v n="$N" '
  function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
  $1 == "L" { nl++; ltitle[nl] = $2; lgenre[nl] = $4; lrating[nl] = $5; next }
  $1 == "C" { nc++; ctitle[nc] = trim($2); cauthor[nc] = trim($3); cgenre[nc] = trim($4) }
  END {
    for (round = 1; round <= n && made < n; round++)
      for (i = 1; i <= nl && made < n; i++)
        for (j = 1; j <= nc; j++)
          if (!used[j] && cgenre[j] == lgenre[i] && tolower(ctitle[j]) != tolower(ltitle[i])) {
            used[j] = 1; made++
            why = (lrating[i] != "" ? "you rated " ltitle[i] " " lrating[i] "/5" : "you finished " ltitle[i])
            print ctitle[j] " | " cauthor[j] " | " cgenre[j] " | Because " why " | history"
            break
          }
  }'
