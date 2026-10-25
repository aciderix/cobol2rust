identification division.
program-id. usage-index.
data division.
working-storage section.
01 g.
   05 a pic x value "<".
   05 i usage index.
   05 b pic x value ">".
01 raw redefines g pic x(6).
01 j usage is index.
01 t.
   05 e pic x occurs 5 indexed by k.
01 n pic 9(4).
01 grp-idx usage index.
   05 gi1.
   05 gi2.
01 xg.
   05 x1 pic x(4).
procedure division.
    set i to 258
    display raw
    set k to 3
    set j to k
    set i to j
    display i " " j
    set n to i
    display n
    set j up by 2
    display j
    if j = 5 display "j=5" end-if
    if i < j display "i<j" end-if
    set gi1 to 7 set gi2 to gi1
    display gi1 " " gi2
    move i to xg
    display xg
    stop run.
