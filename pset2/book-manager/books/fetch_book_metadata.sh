#!/bin/bash
# Book component: enrich basic book information with metadata.
#
#   in  (arg or stdin):  Dune | Frank Herbert
#   out (stdout):        Dune | Frank Herbert | Science Fiction | 1965 | https://openlibrary.org/works/OL893415W
#
# Where the metadata comes from, in order:
#   1. Open Library's free search API (needs curl + jq and a network connection)
#   2. the offline catalog, via the data layer
#   3. nothing found -> genre "Unknown", year left empty
# Which source answered is reported on stderr, so stdout stays one clean line.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/data/book_database.sh"

line="$1"; [ -n "$line" ] || IFS= read -r line
field() { echo "$line" | awk -F'|' -v i="$1" '{ s = $i; gsub(/^[ \t]+|[ \t]+$/, "", s); print s }'; }
title=$(field 1); author=$(field 2)
[ -n "$title" ] || { echo "usage: fetch_book_metadata.sh \"Title | Author\"" >&2; exit 1; }

# Map Open Library's free-form subjects ("Detective and mystery stories", ...) onto
# the small genre vocabulary this app uses everywhere else. First matching rule wins.
map_genre() {
  awk -v subjects="$1" 'BEGIN {
    n = split(tolower(subjects), s, ";")
    split("mystery|detective|crime|murder;science fiction;artificial intelligence|machine learning|computer|programming|software;statistic|probability|forecast|data;psycholog|cognit|decision making;sociolog|social|community;poetry;philosoph;econom;biograph|memoir;cook|food;climate;nature|ecology;music;sport;travel;graphic novel|comic;mathemat;science|biology|physics;history|historical", rule, ";")
    split("Mystery;Science Fiction;AI & Computing;Data Science & Statistics;Psychology;Sociology;Poetry;Philosophy;Economics;Memoir;Food;Climate;Nature;Music;Sports;Travel;Graphic Novel;Math;Science;History", name, ";")
    for (r = 1; r <= 20; r++) for (i = 1; i <= n; i++) if (s[i] ~ rule[r]) { print name[r]; exit }
    for (i = 1; i <= n; i++) if (s[i] ~ /fiction|novel/ && s[i] !~ /non-?fiction/) { print "Fiction"; exit }
    print "Unknown" }'
}

from_open_library() {
  [ -z "$BOOK_OFFLINE" ] && command -v curl >/dev/null && command -v jq >/dev/null || return 1
  local json row
  json=$(curl -fsS --max-time 8 -G "https://openlibrary.org/search.json" \
           --data-urlencode "title=$title" ${author:+--data-urlencode "author=$author"} \
           -d limit=1 -d fields=key,title,author_name,first_publish_year,subject 2>/dev/null) || return 1
  row=$(echo "$json" | jq -r '.docs[0] // empty
          | [.title, (.author_name[0] // ""), ((.first_publish_year // "") | tostring),
             ((.subject // []) | .[:40] | join(";")), (.key // "")] | join("\u001f")')
  [ -n "$row" ] || return 1
  IFS=$'\037' read -r t a y subjects key <<< "$row"
  echo "$t | ${a:-$author} | $(map_genre "$subjects") | $y | https://openlibrary.org$key"
}

from_catalog() {
  "$DB" catalog | awk -F'|' -v t="$title" '
    function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
    tolower(trim($1)) == tolower(t) { print trim($1) " | " trim($2) " | " trim($3) " | " trim($4); found = 1; exit }
    END { exit !found }'
}

link="https://openlibrary.org/search?q=$(printf '%s' "$title${author:+ $author}" | tr ' ' '+')"

if   result=$(from_open_library);  then echo "metadata: Open Library" >&2; echo "$result"
elif result=$(from_catalog);       then echo "metadata: offline catalog" >&2; echo "$result | $link"
else                                    echo "metadata: not found" >&2; echo "$title | $author | Unknown |  | $link"
fi
