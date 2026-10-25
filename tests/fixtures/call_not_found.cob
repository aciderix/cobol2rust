*> CALL of a module not found without ON EXCEPTION (cob_call_error): the
*> runtime error, the implicit CLOSE warnings and exit status 1.
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
    call "CEE3ABD"
    display "after"
    stop run.
