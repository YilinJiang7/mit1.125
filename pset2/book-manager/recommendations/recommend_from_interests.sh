#!/bin/bash
# Recommendation agent: recommend from the user's interests and goals.
#
# Way of thinking: "You said you care about X, so here is a strong book about X."
#   input:  data/interests.txt (via the data layer) -> "interest | keywords"
#   output: candidate lines on stdout ->  Title | Author | Genre | Reason | interests
#   stderr: one line saying which brain was used (codex or offline catalog)
# Ignores ratings on purpose: that is the history agent's job.

HERE="$(cd "$(dirname "$0")" && pwd)"
DB="$HERE/../data/book_database.sh"
N="${BOOK_PER_AGENT:-6}"

interests=$("$DB" interests)
if [ -z "$interests" ]; then
  echo "interests agent: data/interests.txt is empty" >&2
  exit 0
fi

prompt="You are a book recommendation agent that works ONLY from the reader's stated interests.
Interests (name | keywords):
$interests

Books already in the library (do not recommend these):
$("$DB" list | cut -d'|' -f1)

Recommend $N excellent books, spread across different interests.
Reply with exactly $N lines and nothing else, each in this format:
Title | Author | Genre | Reason
Genre must be one of: $("$DB" genres | tr '\n' ',' | sed 's/,$//').
Reason: at most 12 words, and name the interest it serves."

if ideas=$("$HERE/ask_codex.sh" "$prompt"); then
  echo "interests agent: codex" >&2
  echo "$ideas" | head -n "$N" | sed 's/$/ | interests/'
  exit 0
fi

echo "interests agent: offline catalog" >&2
sleep "${BOOK_THINK_SECONDS:-$((RANDOM % 3 + 1))}"   # simulated think time, so progress is visible

# Offline: a catalog book matches an interest when one of the interest's keywords is a word
# of the book's genre (strong match) or one of its tags (weak match). Interests take turns,
# each picking its strongest unused match, so every interest is represented.
{ echo "$interests" | sed 's/^/I|/'
  "$DB" catalog | awk -v seed="$RANDOM" 'BEGIN { srand(seed) } { print rand() "\t" $0 }' | sort -n | cut -f2- | sed 's/^/C|/'
} | awk -F'|' -v n="$N" -v seed="$RANDOM" '
  function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
  $1 == "I" { ni++; name[ni] = trim($2); keys[ni] = "," tolower($3) ","; gsub(/[ \t]*,[ \t]*/, ",", keys[ni]); next }
  $1 == "C" { nc++; title[nc] = trim($2); author[nc] = trim($3); genre[nc] = trim($4); tags[nc] = tolower($6) }
  function match_score(i, j,   k, t, x) {     # 2 = keyword is a word of the genre, 1 = a tag
    k = split(keys[i], t, ",")
    for (x = 1; x <= k; x++) if (t[x] != "" && index(" " tolower(genre[j]) " ", " " t[x] " ")) return 2
    k = split(tags[j], t, ",")
    for (x = 1; x <= k; x++) if (index(keys[i], "," trim(t[x]) ",")) return 1
    return 0
  }
  END {
    srand(seed); start = int(rand() * ni)          # random first interest, so all get a turn over time
    for (round = 1; round <= n && made < n; round++)
      for (step = 0; step < ni && made < n; step++) {
        i = (start + step) % ni + 1; best = 0
        for (j = 1; j <= nc; j++) if (!used[j] && match_score(i, j) > match_score(i, best)) best = j
        if (best) {
          used[best] = 1; made++
          print title[best] " | " author[best] " | " genre[best] " | Serves your interest in " name[i] " | interests"
        }
      }
  }'
