identification division.
program-id. file-no-newline.
environment division.
input-output section.
file-control.
    select f assign to "source.txt" organization line sequential file status fs.
data division.
file section.
fd f.
01 rec pic x(8).
working-storage section.
01 fs pic xx.
procedure division.
    open input f
    perform 4 times
        read f at end display "END" end-read
        display fs "[" rec "]"
    end-perform
    close f
    stop run.
