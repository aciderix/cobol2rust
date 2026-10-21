identification division.
program-id. arithmetic.
data division.
working-storage section.
01 a pic s9(4)v99 value -10.25.
01 b pic s9(4)v99 value 2.50.
01 c pic s9(4)v99 value 0.
01 d pic s9(4)v99 value 0.
procedure division.
    add 1.20 2.30 to a
    display a
    subtract 1 2 from a giving c rounded
    display c
    multiply b by c giving d rounded
    display d
    divide 3 into d giving a rounded
    display a
    compute c rounded = (1 + 2) * -0.125
    display c
    compute c = -1.239
    display c
    compute c rounded = -1.235
    display c
    compute c = 0.1 + 0.2
    if c = 0.3 display "EXACT" end-if
    stop run.
