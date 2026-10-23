*> PERFORM VARYING ... AFTER: reset and test order of nested levels as in cobc.
identification division.
program-id. perform-after.
data division.
working-storage section.
01 i pic s99 value 0.
01 j pic s99 value 0.
01 k pic s99 value 0.
01 n pic 999 value 0.
procedure division.
    perform varying i from 1 by 1 until i > 3 after j from 1 by 1 until j > 2
        display "B " i j
    end-perform
    display "END-B " i " " j
    perform with test after varying i from 1 by 1 until i > 2 after j from 1 by 1 until j > 2
        display "A " i j
    end-perform
    display "END-A " i " " j
    *> The inner FROM depends on the outer variable, the outer UNTIL on the inner one.
    perform varying i from 1 by 2 until i > 5 or j > 8 after j from i by 3 until j > 7
        display "D " i j
    end-perform
    display "END-D " i " " j
    move 0 to n
    perform varying i from 1 until i > 2 after j from 1 until j > 2 after k from j by 1 until k > 3
        add 1 to n
    end-perform
    display "THREE " n " " i " " j " " k
    perform cycle varying i from 3 by -1 until i < 1 after j from 0 by 1 until j = i
    display "END-C " i " " j " " n
    stop run.
cycle.
    add 10 to n.
