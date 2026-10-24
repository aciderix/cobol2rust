identification division.
program-id. display-truncation.
data division.
working-storage section.
01 g.
   05 a pic 99 value 95.
   05 b pic s99 value -95.
   05 c pic s9v9 value 0.
   05 d pic 9p value 90.
   05 e pic s99 sign leading separate value 0.
   05 f pic s99 value 0.
procedure division.
    add 7 to a
    subtract 7 from b
    compute c = 12.34 * 2
    add 150 to d
    compute e = -1234
    compute f rounded = -99.5 - 0.6
    display g
    compute f = -100
    display g
    add 1 to f
    display f
    multiply 50 by a
    divide 3 into b
    display g
    stop run.
