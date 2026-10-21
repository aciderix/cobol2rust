identification division.
program-id. paragraph-flow.
data division.
working-storage section.
01 i pic 99 value 0.
procedure division.
    perform inc-one 2 times
    perform inc-one thru inc-two
    display "I=" i
    perform finish
    display "UNREACHABLE"
    stop run.
inc-one.
    add 1 to i
    exit paragraph
    display "UNREACHABLE".
inc-two.
    add 2 to i.
finish.
    display "STOP IN PERFORM"
    stop run.
