identification division.
program-id. accept-input.
data division.
working-storage section.
01 n pic 99.
01 m pic s9(3)v9.
01 x pic x(4).
procedure division.
    accept n display "[" n "]"
    accept m display "[" m "]"
    accept x display "[" x "]"
    accept n display "[" n "]"
    accept x display "[" x "]"
    stop run.
