identification division.
program-id. negative-zero.
data division.
working-storage section.
01 g.
 05 a pic s99.
 05 b pic s99 comp-3.
 05 c pic s99 comp.
 05 d pic s99 sign leading separate.
 05 e pic s9v9.
 05 f pic 99.
procedure division.
    move -0 to a b c d e f
    display g
    if a = 0 and a = zero display "zero" end-if
    if a < 0 display "neg" end-if
    move -0.0 to e
    display e
    stop run.
