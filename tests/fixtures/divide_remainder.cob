identification division.
program-id. divide-remainder.
data division.
working-storage section.
01 a pic s9(4)v99 value 100.
01 b pic s9(3) value 7.
01 q pic s9(3).
01 qd pic s9(3)v9.
01 r pic s9(3)v99.
01 r2 pic s9v9.
01 s pic 9(4).
01 x pic 99 value 12.
01 y pic 99 value 30.
procedure division.
    divide b into a giving q remainder r
    display q " " r
    divide a by b giving qd rounded remainder r
    display qd " " r
    divide -100 by 7 giving q remainder r
    display q " " r
    divide 22 into a giving qd remainder r2
    display qd " " r2
    divide a by 0 giving q remainder r on size error display "size" end-divide
    display q " " r
    add x y giving s
    display s
    add x y 5 giving s rounded
    display s
    divide x by 5 giving q
    display q
    divide 1000 by 3 giving q remainder r on size error display "size2" not on size error display "ok2" end-divide
    display q " " r
    stop run.
