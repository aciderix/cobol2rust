identification division.
program-id. loops.
data division.
working-storage section.
01 i pic 99 value 0.
01 n pic 99 value 3.
01 acc pic 999 value 0.
procedure division.
    perform n times
        add 1 to acc
        move 1 to n
    end-perform
    display "COUNT=" acc
    perform until i >= 3
        add 1 to i
    end-perform
    display "UNTIL=" i
    perform with test after until i >= 3
        add 1 to i
    end-perform
    display "AFTER=" i
    perform varying i from 1 by 1 until i > 3
        display "BEFORE=" i
    end-perform
    display "FINAL=" i
    perform with test after varying i from 1 by 1 until i > 3
        display "AFTER-V=" i
    end-perform
    display "FINAL-V=" i
    stop run.
