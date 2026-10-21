identification division.
program-id. tables-demo.
data division.
working-storage section.
01 database-a.
    05 row-a occurs 3 times.
        10 label-a pic x(3) value "ROW".
        10 amount pic 9(3)v99 value 1.25.
        10 tag-a occurs 2 times pic xx value "AA".
01 i pic 99 value 0.
01 j pic 99 value 0.
01 total pic 9(4)v99 value 0.
procedure division.
    display "INITIAL=[" database-a "]"
    perform varying i from 1 by 1 until i > 3
        compute amount(i) = i * 2.50
        add amount(i) to total
        perform varying j from 1 by 1 until j > 2
            if j = 2 move "BB" to tag-a(i,j) end-if
        end-perform
        display "ROW=[" row-a(i) "] AMOUNT=" amount(i)
    end-perform
    display "TOTAL=" total
    move amount(1) to amount(2) amount(3)
    initialize row-a(2)
    display "UPDATED=[" database-a "]"
    initialize database-a
    display "INIT=[" database-a "]"
    stop run.
