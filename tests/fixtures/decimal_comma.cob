identification division.
program-id. decimal-comma-case.
environment division.
configuration section.
special-names.
    currency sign is "W"
    decimal-point is comma.
data division.
working-storage section.
01 n pic 9(5)v99.
01 e pic z.zz9,99.
01 c pic www9,99.
01 m pic -9(4),9.
01 t pic x(8).
01 k pic 9(3)v9.
procedure division.
    move 1234,5 to n. move n to e. display "[" e "]".
    move n to c. display "[" c "]".
    compute m = -12,25. display "[" m "]".
    display 1,5 " " 0,25.
    move "12,5" to t. move t to k. display k.
    move e to k. display k.
    move function numval("3,75") to k. display k.
    move function numval-c("W3,75") to k. display k.
    if 1,5 = 1,50 display "eq" end-if.
    display n.
    stop run.
