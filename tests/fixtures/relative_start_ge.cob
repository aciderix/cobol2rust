identification division.
program-id. relative-start-ge.
environment division.
input-output section.
file-control.
    select f assign to "REL1" organization relative access dynamic relative key k file status fs.
data division.
file section.
fd f.
01 r pic x(4).
working-storage section.
01 k pic 9(4).
01 fs pic xx.
procedure division.
    open output f
    move 2 to k move "BBBB" to r write r
    move 5 to k move "EEEE" to r write r
    close f
    open input f
    move 3 to k
    start f key >= k display fs
    read f next display fs " " r " " k
    move 5 to k
    start f key is greater than or equal to k display fs
    read f next display fs " " r " " k
    move 6 to k
    start f key >= k invalid key display "invalid " fs end-start
    close f
    stop run.
