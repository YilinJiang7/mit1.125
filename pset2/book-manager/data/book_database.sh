#!/bin/bash
# Data abstraction layer.
# IMPORTANT: This is the only application file that directly reads/writes books.csv
# (and the other files in data/: catalog.txt, interests.txt, settings.txt).
#
# Everyone else asks for data with a sub-command and gets back "pipe records":
#
#   title | author | genre | year | status | rating | finished | takeaway | link
#
# so no other file needs to know that the storage is CSV (or how CSV quoting works).
#
#   book_database.sh list                        every book, one record per line
#   book_database.sh search TERM                 books where any text field contains TERM
#   book_database.sh get TITLE                   one book (exact title, any case)
#   book_database.sh exists TITLE                exit 0 if the book is already saved
#   book_database.sh add [RECORD]                save a book (RECORD as $1 or one line on stdin)
#   book_database.sh update TITLE FIELD VALUE    change one field
#   book_database.sh update-status TITLE STATUS  (owned | want-to-read | reading | finished)
#   book_database.sh update-rating TITLE 1-5
#   book_database.sh interests | catalog | genres
#   book_database.sh goal | set-goal N           yearly reading goal

DIR="$(cd "$(dirname "$0")" && pwd)"
DB="${BOOK_DB_FILE:-$DIR/books.csv}"
SETTINGS="${BOOK_SETTINGS_FILE:-$DIR/settings.txt}"
CATALOG="$DIR/catalog.txt"
INTERESTS="$DIR/interests.txt"

HEADER="title,author,genre,year,status,rating,finished,takeaway,link"
FIELDS="title author genre year status rating finished takeaway link"
STATUSES="owned want-to-read reading finished"

# Shared awk helpers: parse() splits one CSV line (handles "quoted, fields"),
# csv() quotes a value for writing, rec() turns parsed fields into a pipe record.
AWK_LIB='
function parse(line, f,   n, i, c, v, q) {
  n = 0; v = ""; q = 0
  for (i = 1; i <= length(line); i++) {
    c = substr(line, i, 1)
    if (q && c == "\"" && substr(line, i + 1, 1) == "\"") { v = v c; i++ }
    else if (c == "\"") q = !q
    else if (c == "," && !q) { f[++n] = v; v = "" }
    else v = v c
  }
  f[++n] = v
  for (i = n + 1; i <= 9; i++) f[i] = ""
  return n
}
function csv(s) { if (s ~ /[",]/) { gsub(/"/, "\"\"", s); s = "\"" s "\"" }; return s }
function trim(s) { gsub(/^[ \t\r]+|[ \t\r]+$/, "", s); return s }
function rec(f,   i, out) { out = f[1]; for (i = 2; i <= 9; i++) out = out " | " f[i]; return out }
'

die() { echo "book_database: $*" >&2; exit 1; }
[ -f "$DB" ] || echo "$HEADER" > "$DB"

field_index() {            # "rating" -> 6
  local i=1 name
  for name in $FIELDS; do [ "$name" = "$1" ] && { echo "$i"; return 0; }; i=$((i + 1)); done
  return 1
}

check_value() {            # validate status / rating before anything is written
  case "$1" in
    status) case " $STATUSES " in *" ${2:-want-to-read} "*) ;; *) die "status must be one of: $STATUSES" ;; esac ;;
    rating) case "$2" in ""|[1-5]) ;; *) die "rating must be 1-5" ;; esac ;;
  esac
}

list()   { awk "$AWK_LIB"' NR > 1 && NF { parse($0, f); print rec(f) }' "$DB"; }

search() {                 # match on title/author/genre/status/takeaway, not the link
  awk -v term="$1" "$AWK_LIB"'
    NR > 1 && NF { parse($0, f)
      text = tolower(f[1] " " f[2] " " f[3] " " f[4] " " f[5] " " f[8])
      if (index(text, tolower(term))) print rec(f) }' "$DB"
}

get() {
  awk -v t="$1" "$AWK_LIB"'
    NR > 1 && NF { parse($0, f); if (tolower(trim(f[1])) == tolower(trim(t))) { print rec(f); exit } }' "$DB"
}

exists() { [ -n "$(get "$1")" ]; }

add() {
  local line="$1"
  [ -n "$line" ] || IFS= read -r line
  pick() { echo "$line" | awk -F'|' -v i="$1" '{ s = $i; gsub(/^[ \t]+|[ \t]+$/, "", s); print s }'; }
  local title; title=$(pick 1)
  [ -n "$title" ] || die "a book needs a title"
  exists "$title" && { echo "book_database: \"$title\" is already in your library" >&2; exit 2; }
  check_value status "$(pick 5)"
  check_value rating "$(pick 6)"
  echo "$line" | awk -F'|' "$AWK_LIB"'{
      out = ""
      for (i = 1; i <= 9; i++) {
        v = trim($i); if (i == 5 && v == "") v = "want-to-read"
        out = out (i > 1 ? "," : "") csv(v) }
      print out }' >> "$DB"
}

update() {                 # rewrite the file with one field changed, then swap it in
  local title="$1" name="$2" value="$3" col tmp
  col=$(field_index "$name") || die "unknown field '$name' (fields: $FIELDS)"
  [ "$col" -eq 1 ] && die "the title is the key; it cannot be changed"
  check_value "$name" "$value"
  exists "$title" || die "\"$title\" is not in your library"
  value=$(printf '%s' "$value" | tr '|' '/')   # "|" is the record separator
  tmp="$DB.tmp.$$"
  awk -v t="$title" -v c="$col" -v v="$value" "$AWK_LIB"'
    NR == 1 || !NF { print; next }
    { parse($0, f)
      if (tolower(trim(f[1])) == tolower(trim(t))) f[c] = v
      out = csv(f[1]); for (i = 2; i <= 9; i++) out = out "," csv(f[i]); print out }' "$DB" > "$tmp" &&
    mv "$tmp" "$DB"
}

no_comments() { grep -v '^[[:space:]]*#' "$1" | grep -v '^[[:space:]]*$'; }

cmd="$1"; [ $# -gt 0 ] && shift
case "$cmd" in
  list)          list ;;
  search)        search "$1" ;;
  get)           get "$1" ;;
  exists)        exists "$1" ;;
  add)           add "$1" ;;
  update)        update "$1" "$2" "$3" ;;
  update-status) update "$1" status "$2" ;;
  update-rating) update "$1" rating "$2" ;;
  interests)     no_comments "$INTERESTS" ;;
  catalog)       no_comments "$CATALOG" ;;
  genres)        no_comments "$CATALOG" | awk -F'|' '{ gsub(/^[ \t]+|[ \t]+$/, "", $3); print $3 }' | sort -u ;;
  goal)          goal=$(grep '^reading_goal=' "$SETTINGS" 2>/dev/null | cut -d= -f2); echo "${goal:-12}" ;;
  set-goal)      case "$1" in ''|*[!0-9]*) die "goal must be a number" ;; esac
                 echo "reading_goal=$1" > "$SETTINGS" ;;
  *)             sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
