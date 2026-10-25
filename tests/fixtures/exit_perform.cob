*> EXIT PERFORM and EXIT PERFORM CYCLE in every inline PERFORM form,
*> PERFORM UNTIL EXIT and FOREVER (codegen.c exit_label / cycle_label).
identification division.
program-id. exit-perform.
data division.
working-storage section.
01 i pic 99.
01 j pic 99.
01 n pic 99 value 0.
01 trace pic x(60) value spaces.
01 p pic 99 value 1.
procedure division.
    move 0 to i
    perform until exit
        add 1 to i
        if i = 3
            exit perform cycle
        end-if
        if i > 5
            exit perform
        end-if
        display "until exit " i
    end-perform
    display "after until exit " i
    perform varying i from 1 by 1 until i > 4
        perform varying j from 1 by 1 until j > 4
            if j = 2 exit perform cycle end-if
            if j = 4 exit perform end-if
            display "varying " i " " j
        end-perform
        if i = 3 exit perform end-if
    end-perform
    display "after varying " i " " j
    perform with test after varying i from 1 by 1 until i > 3
        if i = 2 exit perform cycle end-if
        display "test after " i
    end-perform
    move 0 to n
    perform 4 times
        add 1 to n
        if n = 2 exit perform cycle end-if
        display "times " n
    end-perform
    perform
        display "once before"
        exit perform
        display "never"
    end-perform
    perform
        exit perform cycle
        display "never"
    end-perform
    move 0 to i
    perform forever
        add 1 to i
        if i = 3 exit perform end-if
    end-perform
    display "forever " i
    move 0 to i
    perform with test after until i > 2
        add 1 to i
        evaluate i
            when 2 exit perform cycle
            when other display "evaluate " i
        end-evaluate
    end-perform
    perform body-para 2 times
    stop run.
body-para.
    perform until exit
        display "in paragraph"
        exit perform
    end-perform.
