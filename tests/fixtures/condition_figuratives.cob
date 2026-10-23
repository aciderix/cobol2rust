identification division.
program-id. condition-figuratives.
data division.
working-storage section.
01 f pic x(5) value "BACBA".
   88 d value all "BAC".
   88 q value quote.
01 grp.
   05 pic x(3) value "XYZ".
   05 pic x(2) value zero.
   05 named pic 9 value 4.
01 z pic x(3) value zeros.
procedure division.
    display "[" grp "][" z "]"
    if d display "d1" else display "not d1" end-if
    move "BACB" to f
    if d display "d2" else display "not d2" end-if
    move all '"' to f
    if q display "q" end-if
    stop run.
