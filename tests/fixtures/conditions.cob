identification division.
program-id. conditions.
data division.
working-storage section.
01 a pic 99 value 7.
01 b pic 99 value 4.
01 txt pic x(5) value "AB".
procedure division.
    if (a > b and b < 9) or a = 0
        display "BOOL"
    end-if
    if (a + b) > 10
        display "PAREN"
    end-if
    if a is not equal to b display "NE" end-if
    if a is greater than or equal to 7 display "GE" end-if
    if b is less than or equal to 4 display "LE" end-if
    if not a < b display "NOT" end-if
    if txt = "AB" display "PAD" end-if
    if a = 7
        if b = 0 display "BAD" else display "INNER" end-if
    else
        display "BAD"
    end-if
    if a = 7 display "PERIOD".
    display "AFTER"
    stop run.
