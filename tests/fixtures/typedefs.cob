identification division.
program-id. typedefs.
*> TYPEDEF, TYPE TO, USAGE type-name, SAME AS (copy_into_field).
data division.
working-storage section.
01 int-t       is typedef binary-long.
01 money-t     is typedef pic s9(3)v99 sign leading separate value -1.5.
01 name-t      typedef pic x(6) justified right.
01 point-t     is typedef.
   05 px       pic 99 value 7.
   05 py       pic 99.
   05 pxy      redefines py pic xx.
   05 flag     pic x value "n".
      88 is-on value "y".
01 counter     usage int-t value 41.
01 amount      type to money-t.
01 nm          usage name-t.
01 pts.
   05 pt       type point-t occurs 2.
   05 tail     pic x value "|".
01 one-pt      type point-t.
01 same-amt    same as amount.
01 same-pts    same as pts.
procedure division.
    add 1 to counter
    display counter " " function length (counter)
    display amount " " function length (amount)
    move 12.34 to amount
    display amount
    move "ab" to nm
    display "[" nm "]"
    display "[" pts "] " function length (pts)
    move 3 to py of pt of pts (2)
    set is-on of pt of pts (1) to true
    display "[" pts "] " pxy of pt of pts (2)
    if is-on of pt of pts (1) display "on" end-if
    display "[" one-pt "] [" same-amt "] [" same-pts "]"
    stop run.
