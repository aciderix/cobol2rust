identification division.
program-id. ls-variable.
environment division.
input-output section.
file-control.
    select f assign to "VAR.TXT" organization line sequential file status fs.
    select g assign to "MIN.TXT" organization line sequential file status fs.
data division.
file section.
fd f.
01 short-rec pic x(3).
01 long-rec.
    02 long-a pic x(4).
    02 long-b pic x(4).
fd g record varying from 5 to 10 depending on n.
01 g-rec pic x(10).
working-storage section.
01 fs pic xx.
01 x pic x(10).
01 n pic 99.
procedure division.
    open output f.
    move "ABC" to short-rec.
    write short-rec.
    display "w1 " fs.
    move "LONGREC1" to long-rec.
    write long-rec.
    display "w2 " fs.
    move "XY" to short-rec.
    write short-rec.
    write long-rec from "Z".
    display "w4 " fs.
    close f.
    open input f.
    perform 5 times
        move all "*" to x
        read f into x
        display "r " fs " [" x "] [" long-rec "] [" short-rec "]"
    end-perform.
    close f.
    *> finalize_file: a LINE SEQUENTIAL record_min is 0.
    open output g.
    move "ABCDEFGHIJ" to g-rec.
    move 2 to n.
    write g-rec.
    display "g " fs.
    move 0 to n.
    write g-rec.
    display "g " fs.
    move 10 to n.
    write g-rec.
    close g.
    open input g.
    perform 4 times
        read g into x
        display "g " fs " " n " [" g-rec "] [" x "]"
    end-perform.
    close g.
    stop run.
