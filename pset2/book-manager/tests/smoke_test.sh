#!/bin/bash
# Smoke test (added file): checks every non-interactive component without touching your
# real library. Runs offline on a temporary copy of the data.   Usage: ./tests/smoke_test.sh

cd "$(dirname "$0")/.." || exit 1
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cp data/books.csv "$tmp/books.csv"
export BOOK_DB_FILE="$tmp/books.csv" BOOK_SETTINGS_FILE="$tmp/settings.txt"
export BOOK_AI=offline BOOK_OFFLINE=1 BOOK_THINK_SECONDS=0

pass=0; fail=0
check() {   # check "description" command...
  if "${@:2}" >/dev/null 2>&1; then pass=$((pass + 1)); echo "  ok    $1"
  else fail=$((fail + 1)); echo "  FAIL  $1"; fi
}

echo "data layer"
check "list gives 9-field records"          sh -c 'data/book_database.sh list | awk -F" [|] " "NF != 9 { exit 1 }"'
check "a title with a comma round-trips"     sh -c 'data/book_database.sh add "Salt, Fat, Acid, Heat | Samin Nosrat | Food" && data/book_database.sh exists "salt, fat, acid, heat"'
check "duplicates are refused"               sh -c '! data/book_database.sh add "Sapiens | Harari"'
check "bad ratings are refused"              sh -c '! data/book_database.sh update-rating Sapiens 9'
check "status update is stored"              sh -c 'data/book_database.sh update-status "Bowling Alone" reading && data/book_database.sh get "bowling alone" | grep -q "| reading |"'
check "goal can be changed"                  sh -c 'data/book_database.sh set-goal 20 && [ "$(data/book_database.sh goal)" = 20 ]'

echo "book components"
check "search by argument"                   sh -c 'books/search_books.sh kahneman | grep -q "Thinking, Fast and Slow"'
check "search through a pipe"                sh -c 'echo history | books/search_books.sh | grep -q Sapiens'
check "search with a field filter"           sh -c 'books/search_books.sh "rating:5" | awk -F" [|] " "\$6 != 5 { exit 1 }"'
check "metadata from the offline catalog"    sh -c '[ "$(books/fetch_book_metadata.sh "dune")" = "Dune | Frank Herbert | Science Fiction | 1965 | https://openlibrary.org/search?q=dune" ]'
check "unknown books still get a record"     sh -c 'books/fetch_book_metadata.sh "Nope Nope | X" | grep -q "| Unknown |"'

echo "recommendation agents"
for agent in history interests discovery; do
  script=$(ls recommendations/*"$agent"*.sh)
  check "$agent agent: 5-field lines tagged '$agent'" \
        sh -c "out=\$($script) && [ -n \"\$out\" ] && echo \"\$out\" | awk -F' [|] ' 'NF != 5 || \$5 != \"$agent\" { exit 1 }'"
done

echo "refinement"
{ recommendations/recommend_from_history.sh; recommendations/recommend_from_interests.sh
  recommendations/recommend_for_discovery.sh; echo "Sapiens | Harari | History | owned | history"; } 2>/dev/null \
  | recommendations/refine_recommendations.sh > "$tmp/short.txt"
check "shortlist has 1-5 lines"              sh -c "n=\$(grep -c . $tmp/short.txt); [ \$n -ge 1 ] && [ \$n -le 5 ]"
check "books already owned are removed"      sh -c "! grep -q '^Sapiens ' $tmp/short.txt"
check "no duplicate titles"                  sh -c "[ -z \"\$(cut -d'|' -f1 $tmp/short.txt | sort | uniq -d)\" ]"
check "every agent is represented"           sh -c "for a in history interests discovery; do grep -q \$a $tmp/short.txt || exit 1; done"
check "duplicates merge into 'a+b'"          sh -c 'printf "X | A | G | r | history\nx. | A | G | r | discovery\n" | recommendations/refine_recommendations.sh | grep -q "history+discovery"'

echo "parallelism"
start=$(date +%s)
for agent in recommendations/recommend_*.sh; do BOOK_THINK_SECONDS=2 "$agent" > /dev/null 2>&1 & done
wait
check "3 agents x 2s finish in < 4s"          [ $(( $(date +%s) - start )) -lt 4 ]

echo "workflows (headless)"
check "library workflow: prepare + save"      sh -c 'r=$(workflows/manage_library.sh prepare "Dune | Frank Herbert" finished) && workflows/manage_library.sh save "$r" && workflows/manage_library.sh details dune | grep -q "| finished | .* | 20[0-9][0-9]-"'
check "library workflow: already-owned = exit 2" sh -c 'workflows/manage_library.sh prepare "Sapiens" reading; [ $? -eq 2 ]'
check "recommendation workflow: pipe stage"   sh -c 'n=$(workflows/get_recommendations.sh | grep -c .) && [ "$n" -ge 1 ] && [ "$n" -le 5 ]'
check "recommendation workflow: progress events" sh -c 'workflows/get_recommendations.sh --progress 2>&1 >/dev/null | grep -q "^agent discovery"'

echo "architecture: strictly top-down"
code() { grep -v '^[[:space:]]*#' "$@" 2>/dev/null; }      # file contents without comment lines
check "only the data layer touches books.csv"  sh -c '! grep -n "books\.csv" app.sh ui/*.sh workflows/*.sh books/*.sh recommendations/*.sh | grep -v ":[[:space:]]*#"'
check "the UI never skips the workflows"       sh -c "! { $(declare -f code); code ui/*.sh | grep -Eq 'data/|books/|recommendations/'; }"
check "workflows never call the UI"            sh -c "! { $(declare -f code); code workflows/*.sh | grep -q 'ui/'; }"
check "components never call workflows or UI"  sh -c "! { $(declare -f code); code books/*.sh recommendations/*.sh | grep -Eq 'ui/|workflows/'; }"
check "the data layer calls nothing above it"  sh -c "! { $(declare -f code); code data/book_database.sh | grep -Eq 'ui/|workflows/|books/|recommendations/'; }"

echo; echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
