identification division.
program-id. eval-demo.
data division.
working-storage section.
01 n pic 9 value 2.
01 name-a pic x(4) value "AB".
procedure division.
    evaluate n
        when 1 display "ONE"
        when 2 display "TWO" add 1 to n
        when other display "OTHER"
    end-evaluate
    evaluate n
        when 0 display "ZERO"
        when other display "DEFAULT"
    end-evaluate
    evaluate name-a
        when "AB" display "TEXT"
        when other continue
    end-evaluate
    stop run.
