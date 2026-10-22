identification division.
program-id. separators.
data division.
working-storage section.
01 first-a pic 9.
01 second-a pic 9.
01 total-a pic 99 value 0.
01 edited-a pic +9(3).99; value 12.34.
01 label-a pic x(3), value "ABC".
01 grid-a.
  02 row-a occurs 2.
    03 cell-a pic 9 occurs 2.
procedure division.
    move 2 to first-a,second-a
    add 1,2 to total-a
    move 7 to cell-a(1,+2)
    if first-a = 2
        display "VALUES:" first-a;second-a total-a
    else
        display "BAD"
    end-if
    if first-a = 9
        display "BAD";display "ALSO-BAD"
    end-if
    display "TEXT:" "A,B;C";label-a
    display "EDITED:" edited-a
    display "INDEX:" cell-a(1;+2)
    stop run.
