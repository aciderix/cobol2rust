identification division.
program-id. literal-move-case.
data division.
working-storage section.
01 a pic 9(5).
01 b pic s9(3).
01 c pic 9v99.
01 d pic 9(3) comp.
01 e pic s9(3) sign leading separate.
01 f pic 9(3) blank when zero.
procedure division.
    move "12345" to a. display a.
    move "12" to a. display a.
    move "1234567" to a. display a.
    move "12" to b. display b.
    move "12" to c. display c.
    move "12" to e. display e.
    move "000" to f. display "[" f "]".
    stop run.
