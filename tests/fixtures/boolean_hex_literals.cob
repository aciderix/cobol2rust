identification division.
program-id. bh.
data division.
working-storage section.
01 x-1 pic 9(2) value b"010101".
01 x-2 pic 9(8) value h"012345".
01 x-3 pic 9(18) value h"fffffffffffffff".
01 x-4 pic 9(5).
procedure division.
    display x-1 " " x-2 " " x-3
    move b'111' to x-4
    display x-4
    compute x-4 = h"FF" + b"1"
    display x-4
    if x-1 = b"10101" display "eq" end-if
    stop run.
