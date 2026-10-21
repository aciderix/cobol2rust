identification division.
program-id. reference-modification.
data division.
working-storage section.
01 text-a pic x(10) value "ABCDEFGHIJ".
01 copy-a pic x(5).
01 numeric-a pic 9(4) value 1234.
01 table-a.
    05 row-a occurs 2 times pic x(5) value "ABCDE".
01 i pic 9 value 2.
procedure division.
    display text-a(2:3) "/" text-a(7:)
    move text-a(2:5) to copy-a
    move "xy" to text-a(3:2)
    display text-a "/" copy-a
    move text-a(1:5) to text-a(3:5)
    display "OVERLAP=" text-a
    move "ZZ" to row-a(i)(2:2)
    display "TABLE=" table-a
    move "99" to numeric-a(2:2)
    display "NUMBER=" numeric-a
    if numeric-a(2:2) is numeric display "SLICE-NUMERIC" end-if
    initialize row-a(1)(2:2)
    display "INIT=" table-a
    initialize numeric-a(2:2)
    display "RAW=" numeric-a(1:)
    if numeric-a is not numeric display "NUMERIC-DATA-INVALID" end-if
    stop run.
