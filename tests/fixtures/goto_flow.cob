identification division.
program-id. goto-flow.
data division.
working-storage section.
01 count-a pic 9 value 0.
01 choice pic 9 value 2.
procedure division.
    perform process-area
    display "RETURN"
    stop run.
process-area section.
start-p.
    add 1 to count-a
    display "PASS" count-a
    if count-a = 1 go outside-p end-if
    go first-p second-p depending on choice
    display "BAD".
first-p.
    display "BAD"
    exit section.
second-p.
    display "SECOND"
    exit section.
outside-area section.
outside-p.
    display "DETOUR"
    go start-p.
