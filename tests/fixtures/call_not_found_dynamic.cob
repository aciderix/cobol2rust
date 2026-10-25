*> The same for a CALL identifier (dynamic name).
identification division.
program-id. t.
environment division.
input-output section.
file-control.
    select f assign to "out.dat" organization line sequential.
data division.
file section.
fd f. 01 r pic x(3).
working-storage section.
01 n pic x(8) value "DYNPROG".
procedure division.
    open output f
    display "before"
    call n
    display "after"
    stop run.
