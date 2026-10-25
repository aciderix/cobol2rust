identification division.
program-id. stop-literal.
environment division.
input-output section.
file-control.
    select out-file assign to "STOP.TXT" organization line sequential.
data division.
file section.
fd out-file.
01 out-rec pic x(8).
working-storage section.
01 answer pic x(4).
procedure division.
    display "first".
    accept answer.
    display "answer [" answer "]".
    open output out-file.
    write out-rec from "WRITTEN".
    close out-file.
    stop "OPERATOR".
    display "after stop".
    accept answer.
    display "second [" answer "]".
    stop run.
