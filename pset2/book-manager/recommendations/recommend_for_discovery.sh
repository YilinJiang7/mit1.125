#!/bin/bash
# Recommendation agent: deliberately explore beyond the user's normal patterns.
#
# Way of thinking: "What have you never tried? Here is a great door into it."
#   input:  genres already in the library + interest keywords (via the data layer)
#   output: candidate lines on stdout ->  Title | Author | Genre | Reason | discovery
#   stderr: one line saying which brain was used (codex or offline catalog)
# Optimizes for novelty, not similarity: at most one pick per unfamiliar genre.

HERE="$(cd "$(dirname "$0")" && pwd)"
DB="$HERE/../data/book_database.sh"
N="${BOOK_PER_AGENT:-6}"

# The reader's comfort zone: every genre already on the shelf + every interest keyword.
known_genres=$("$DB" list | awk -F'|' '{ g = $3; gsub(/^[ \t]+|[ \t]+$/, "", g); print g }' | sort -u)
keywords=$("$DB" interests | cut -d'|' -f2 | tr ',' '\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | grep . | sort -u)

prompt="You are a book recommendation agent whose job is DISCOVERY: widen the reader's world.
The reader already reads these genres:
$known_genres
and is interested in: $(echo "$keywords" | tr '\n' ',' | sed 's/,$//')

Recommend $N acclaimed, approachable books from genres OUTSIDE that comfort zone,
each from a different genre. Reply with exactly $N lines and nothing else, in this format:
Title | Author | Genre | Reason
Genre must be one of: $("$DB" genres | tr '\n' ',' | sed 's/,$//').
Reason: at most 12 words, and say what new perspective it opens."

if ideas=$("$HERE/ask_codex.sh" "$prompt"); then
  echo "discovery agent: codex" >&2
  echo "$ideas" | head -n "$N" | sed 's/$/ | discovery/'
  exit 0
fi

echo "discovery agent: offline catalog" >&2
sleep "${BOOK_THINK_SECONDS:-4}"   # simulated think time (2/3/4 s per agent), so the progress line
                                   # shows the agents finishing one by one

# Offline: shuffle the catalog, drop anything whose genre or tags touch the comfort zone,
# and keep the first book from each remaining genre.
{ echo "$known_genres" | sed 's/^/K|/'
  echo "$keywords"     | sed 's/^/K|/'
  "$DB" catalog | awk -v seed="$RANDOM" 'BEGIN { srand(seed) } { print rand() "\t" $0 }' | sort -n | cut -f2- | sed 's/^/C|/'
} | awk -F'|' -v n="$N" '
  function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
  $1 == "K" { known[tolower(trim($2))] = 1; next }
  $1 == "C" && made < n {
    genre = trim($4)
    if (tolower(genre) in known || genre in picked) next
    k = split($6, t, ","); familiar = 0
    for (x = 1; x <= k; x++) if (tolower(trim(t[x])) in known) familiar = 1
    if (familiar) next
    picked[genre] = 1; made++
    print trim($2) " | " trim($3) " | " genre " | New territory: no " genre " on your shelf yet | discovery"
  }'
