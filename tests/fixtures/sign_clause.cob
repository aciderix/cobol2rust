identification division.
program-id. sign-clause.
data division.
working-storage section.
01 grp.
   05 a pic s9(3) sign leading value -12.
   05 b pic s9(3) sign trailing separate value -12.
   05 c pic s9(3) sign is leading separate character value 34.
   05 d pic s9v99 leading separate value -1.5.
   05 e pic s9(3) value -7.
01 raw redefines grp pic x(16).
01 g2 sign leading separate.
   05 h pic s99 value -5.
   05 i pic 99 value 6.
01 raw2 redefines g2 pic x(5).
01 x6 pic x(6).
01 n pic s9(5).
procedure division.
    display "[" raw "][" raw2 "]"
    display a " " b " " c " " d " " e " " h " " i
    move -345 to a b c
    move 2.25 to d
    display "[" raw "]"
    add 400 to a b c
    display a " " b " " c
    compute b = b * -2
    display b
    move a to x6 display "[" x6 "]"
    move b to x6 display "[" x6 "]"
    move c to x6 display "[" x6 "]"
    move "-0042" to x6
    move x6 to a b c display "[" raw "]"
    move b to n display n
    move -1000 to b c display "[" raw "]"
    if b = 0 display "zero" end-if
    if c is numeric display "numeric" end-if
    initialize grp display "[" raw "]"
    stop run.
