identification division.
program-id. exponentiation.
data division.
working-storage section.
01 c pic s9(5)v9(4).
01 a pic s9v9 value -1.5.
procedure division.
    compute c = 2.0 ** 4
    display c
    compute c = -2 ** 2
    display c
    compute c = 2 ** 3 ** 2
    display c
    compute c = a ** 3
    display c
    move -2 to a
    compute c = 4 ** a
    display c
    compute c = 4 ** a
    display c
    compute c = 1.5 ** 2 * 2 + 1
    display c
    if 2 ** 3 = 8 display "eight" end-if
    if 2 ** 2 ** 3 = 64 display "left" end-if
    stop run.
