identification division.
program-id. zero-demo.
data division.
working-storage section.
01 a pic s9(3)v99 value -0.00.
01 b pic s9(3)v99 value 0.
01 n pic 99 value 0.
01 delta-n pic 99 value 1.
procedure division.
    display "INITIAL=" a
    compute a = -0.001
    display "SMALL=" a
    move a to b
    display "MOVED=" b
    add 0 to a
    display "ADDED=" a
    compute a rounded = -0.0049
    display "ROUND=" a
    perform delta-n times
        display "COUNT=" delta-n
        add 1 to delta-n
    end-perform
    move 1 to delta-n
    perform varying n from 1 by delta-n until n > 6
        display "DYNAMIC=" n
        add 1 to delta-n
    end-perform
    display "FINAL=" n
    stop run.
