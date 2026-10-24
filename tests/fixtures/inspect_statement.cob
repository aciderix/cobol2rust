identification division.
program-id. inspect-statement.
data division.
working-storage section.
01 x pic x(12) value "AABXAYABBA A".
01 y pic x(12).
01 n pic 99 value 0.
01 m pic 9 value 0.
01 counters.
   05 c pic 999 occurs 3.
01 s pic s9(4) value -1234.
01 sl pic s9(4) sign leading value -1234.
01 sp pic s9(3) sign trailing separate value -12.
01 p pic 9p value 0.
01 one pic x value "A".
01 two pic xx value "AB".
01 big pic x(20) value "ab.cd.ef.gh.ij.kl.mn".
procedure division.
    inspect x tallying n for characters
    display n
    move 0 to n
    inspect x tallying n for all "A"
    display n
    move 0 to n
    inspect x tallying n for leading "A" all "A"
    display "leading-quirk " n
    move 0 to n
    inspect x tallying n for all "AB" all "A" all "B"
    display n
    move 0 to n
    inspect x tallying n for characters before initial "X"
    display n
    move 0 to n
    inspect x tallying n for characters after initial "Y"
    display n
    move 0 to n
    inspect x tallying n for all "A" after "X" before "B"
    display n
    move 0 to n
    inspect x tallying n for all "A" before "B" after "X"
    display n
    move 0 to n
    inspect x tallying n for all space
    display n
    move 0 to n
    inspect x tallying n for trailing "A"
    display n
    move 0 to n
    inspect x tallying n for characters after "Q"
    display n
    move zero to counters
    inspect x tallying c(1) for all "A" c(2) for all "B" c(3) for characters
    display counters
    move 0 to m
    inspect big tallying m for characters
    display "m " m
    move 0 to p
    inspect big tallying p for characters
    display "p " p
    move x to y
    inspect y replacing all "A" by "Z"
    display y
    move x to y
    inspect y replacing leading "A" by "-" first "B" by "*"
    display y
    move x to y
    inspect y replacing characters by "." after initial "X" before initial " "
    display y
    move x to y
    inspect y replacing all "AB" by "12" all "A" by "#"
    display y
    move x to y
    inspect y replacing first "A" by "q" "B" by "r"
    display y
    move x to y
    inspect y replacing all "A" by all "*"
    display y
    move x to y
    inspect y replacing all "AB" by zero
    display y
    move x to y
    inspect y replacing all "AB" by "ZZ" trailing "A" by "t"
    display y
    move x to y
    inspect y replacing all one by two(2:1)
    display y
    move x to y
    inspect y tallying n for all "A" replacing all "A" by "a"
    display y " " n
    move x to y
    inspect y converting "ABXY" to "abxy"
    display y
    move x to y
    inspect y converting "AAB" to "123" after "X"
    display y
    move x to y
    inspect y converting "AB" to quote
    display y
    move x to y
    inspect y(3:5) replacing all "A" by "+"
    display y
    inspect s replacing all "2" by "9"
    display s
    inspect sl converting "1234" to "5678"
    display sl
    inspect sp replacing all "-" by "+"
    display sp
    inspect s tallying n for all "3"
    display s " " n
    stop run.
