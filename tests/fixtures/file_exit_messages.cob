*> libcob at the end of the run unit: implicit CLOSE warnings for the files
*> left open (latest OPEN first, missing OPTIONAL omitted), after the fatal
*> error of a file without FILE STATUS (cob_fatal_error, exit status 1).
identification division.
program-id. t.
environment division.
input-output section.
file-control.
    select first-out assign to "a.dat" organization line sequential.
    select Second-Out assign to dd-name organization line sequential.
    select optional opt-in assign to "missing.dat" organization line sequential.
    select must-in assign to "absent.dat" organization line sequential.
data division.
file section.
fd first-out. 01 r1 pic x(3).
fd Second-Out. 01 r2 pic x(3).
fd opt-in. 01 r3 pic x(3).
fd must-in. 01 r4 pic x(3).
procedure division.
    open output first-out
    open output Second-Out
    open input opt-in
    display "before"
    open input must-in
    display "after"
    stop run.
