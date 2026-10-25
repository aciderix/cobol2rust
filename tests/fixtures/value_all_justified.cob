identification division.
program-id. value-all-justified.
data division.
working-storage section.
01 a pic x(10) value all quote.
01 b pic x(5) value all "ab".
01 c pic x(4) value all spaces.
01 g value all "xy".
   05 g1 pic x(3).
   05 g2 pic x(2).
01 j pic x(6) justified right value "ab".
01 k pic x(4) just.
procedure division.
    display "[" a "][" b "][" c "][" g "][" j "]"
    move "abc" to j k display "[" j "][" k "]"
    move "abcdefgh" to j k display "[" j "][" k "]"
    move g to j display "[" j "]"
    move spaces to j display "[" j "]"
    move all "z" to j display "[" j "]"
    move 12 to j display "[" j "]"
    initialize j display "[" j "]"
    stop run.
