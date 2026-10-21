identification division.
program-id. file-simple-demo.
environment division.
input-output section.
file-control.
    select f assign to "simple.txt" organization line sequential.
data division.
file section.
fd f.
01 rec pic x(8).
working-storage section.
01 done pic 9 value 0.
procedure division.
    open output f
    write rec from "OK"
    close f
    open input f
    perform until done = 1
        read f
            at end move 1 to done
            not at end display "[" rec "]"
        end-read
    end-perform
    close f
    stop run.
