#!/bin/bash
# Recommendation component: read candidates from stdin and produce a refined shortlist.
#
#   stdin:  Title | Author | Genre | Reason | source      (from the three agents, any order)
#   stdout: Title | Author | Genre | Reason | sources     (at most BOOK_SHORTLIST lines, default 5)
#
#   cat recommendations.txt | ./recommendations/refine_recommendations.sh
#
# The refinement is itself a pipeline of five small steps:
#   clean -> drop_owned -> merge_duplicates -> rank -> shortlist

DB="$(cd "$(dirname "$0")/.." && pwd)/data/book_database.sh"
LIMIT="${BOOK_SHORTLIST:-5}"
TAB=$(printf '\t')

# 1. keep only well-formed lines, with whitespace trimmed
clean() {
  awk -F'|' 'function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
    NF == 5 && trim($1) != "" {
      print trim($1) " | " trim($2) " | " trim($3) " | " trim($4) " | " trim($5) }'
}

# 2. remove books that are already in the library (asks the data layer, one title at a time)
drop_owned() {
  while IFS= read -r line; do
    "$DB" exists "${line%% | *}" || echo "$line"
  done
}

# 3. the same book from several agents becomes one line, with the agents joined: history+interests
#    "The Dune" / "dune" / "Dune." count as the same title.
merge_duplicates() {
  awk -F' [|] ' '
    { key = tolower($1); sub(/^the /, "", key); gsub(/[^a-z0-9]/, "", key)
      if (!(key in pos)) { pos[key] = ++n; order[n] = key; line[key] = $1 " | " $2 " | " $3 " | " $4
                           src[key] = $5; votes[key] = 1; turn[key] = ++seen[$5] }
      else if (index("+" src[key] "+", "+" $5 "+") == 0) { src[key] = src[key] "+" $5; votes[key]++ } }
    END { for (i = 1; i <= n; i++) { k = order[i]; print votes[k] "\t" turn[k] "\t" i "\t" line[k] " | " src[k] } }'
}

# 4. books several agents agree on come first; then take turns between the agents
#    (each agent's 1st idea, then each agent's 2nd idea, ...), so no agent dominates
rank() { sort -t "$TAB" -k1,1nr -k2,2n -k3,3n | cut -f4-; }

# 5. cut to LIMIT, but first make sure every agent that produced something is represented
shortlist() {
  awk -F' [|] ' -v limit="$LIMIT" '
    { n++; row[n] = $0; src[n] = $5 }
    END {
      for (i = 1; i <= n && taken < limit; i++) {          # pass 1: one per new perspective
        k = split(src[i], s, "+"); fresh = 0
        for (x = 1; x <= k; x++) if (!(s[x] in covered)) fresh = 1
        if (fresh) { keep[i] = 1; taken++; for (x = 1; x <= k; x++) covered[s[x]] = 1 }
      }
      for (i = 1; i <= n && taken < limit; i++) if (!keep[i]) { keep[i] = 1; taken++ }   # pass 2: fill up
      for (i = 1; i <= n; i++) if (keep[i]) print row[i]
    }'
}

clean | drop_owned | merge_duplicates | rank | shortlist
