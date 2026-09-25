#!/bin/bash
# chain.sh PREV NEXT : wait for lanePREV to finish, then run laneNEXT
R=/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm2/repro
until grep -q LANEDONE $R/logs/lane$1.log 2>/dev/null; do sleep 10; done
$R/lane.sh lane$2 $R/lane$2.txt
