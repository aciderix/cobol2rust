identification division.
program-id. close-reel.
environment division.
input-output section.
file-control.
    select f assign to "REELF" organization sequential file status fs.
    select g assign to "REELG" file status gs.
    select optional h assign to "MISSING-H" organization sequential file status hs.
data division.
file section.
fd f.
01 f-rec pic x(4).
fd g.
01 g-rec pic x(4).
fd h.
01 h-rec pic x(4).
working-storage section.
01 fs pic xx.
01 gs pic xx.
01 hs pic xx.
procedure division.
    open output f g
    move "AAAA" to f-rec write f-rec
    close f reel display "reel " fs
    move "BBBB" to f-rec write f-rec display "write after reel " fs
    close f unit for removal display "unit " fs
    close f with no rewind display "no rewind " fs
    write f-rec display "write after no rewind " fs
    close f display "close again " fs
    move "CCCC" to g-rec write g-rec
    close g no rewind display "g no rewind " gs
    open input h
    close h reel display "missing reel " hs
    open input f
    read f display fs " " f-rec
    close f reel display "input reel " fs
    read f display fs " " f-rec
    close f
    stop run.
