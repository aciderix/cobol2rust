identification division.
program-id. alnum-editing.
data division.
working-storage section.
01 a pic xbx0xbx0x.
01 b pic xx/xx/xx.
01 c pic ababx0a value "ab c0d".
01 d pic x(2)b9(2).
01 n pic s9(4) value -1234.
01 k pic 9(3) comp value 42.
01 g.
   05 g1 pic xx value "GH".
   05 g2 pic 99 value 12.
procedure division.
    display "[" a "][" b "][" c "][" d "]"
    move "ABCDEFGH" to a b c d display "[" a "][" b "][" c "][" d "]"
    move spaces to a b display "[" a "][" b "]"
    move zero to a b display "[" a "][" b "]"
    move "AB" to a b display "[" a "][" b "]"
    initialize a b c d display "[" a "][" b "][" c "][" d "]"
    move n to a d display "[" a "][" d "]"
    move k to a d display "[" a "][" d "]"
    move g to a display "[" a "]"
    move 123 to a display "[" a "]"
    if a = "A B0   0 " display "eq" else display "ne" end-if
    move "AB" to a
    if a = "A B0   0 " display "eq" else display "ne" end-if
    move a to g display "[" g "]"
    stop run.
