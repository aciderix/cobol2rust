identification division.
program-id. file-read-demo.
environment division.
input-output section.
file-control.
    select f assign to "records.txt" organization line sequential file status fs.
data division.
file section.
fd f.
01 rec pic x(4).
working-storage section.
01 fs pic 99.
01 dest pic x(6) value "??????".
procedure division.
    move "ZZZZ" to rec
    open input f
    display "OPEN=" fs "[" rec "]"
    perform 7 times
        read f next record into dest
            at end display "END"
            not at end display "BODY"
        end-read
        display fs "[" rec "][" dest "]"
    end-perform
    close f
    stop run.
