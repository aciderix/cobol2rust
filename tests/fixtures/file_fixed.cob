identification division.
program-id. file-fixed-demo.
environment division.
input-output section.
file-control.
    select f assign to "fixed.txt" organization line sequential file status fs.
data division.
file section.
fd f.
01 rec pic x(8).
working-storage section.
01 fs pic xx.
procedure division.
    open output f
    write rec from "A"
    write rec from spaces
    write rec from "ABCDEFGH"
    close f
    open input f
    perform 3 times
        read f
        display fs "[" rec "]"
    end-perform
    close f
    stop run.
