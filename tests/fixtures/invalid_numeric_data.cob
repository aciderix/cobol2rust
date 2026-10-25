*> Without runtime checks (cobc without -debug), libcob computes with invalid
*> numeric data: each DISPLAY byte counts as its low nibble (COB_D2I), packed
*> digits are read as they are and any sign but D is positive.
identification division.
program-id. invalid-data.
data division.
working-storage section.
01 text-amount pic x(6) value "  12 5".
01 amount redefines text-amount pic 9(4)v99.
01 letters pic x(4) value "AB1C".
01 letter-number redefines letters pic 9(4).
01 junk pic x(5) value "ABCDE".
01 packed redefines junk pic s9(5) comp-3.
01 total pic 9(6)v99 value 0.
01 result pic s9(6) comp-3.
01 count-value pic 9(4) value 0.
procedure division.
    add amount to total
    display "total " total
    compute count-value = letter-number + 1
    display "letters " count-value
    if amount > 100 display "amount > 100" else display "amount <= 100" end-if
    if letter-number = 1213 display "letters = 1213" end-if
    compute result = packed + 1
    display "packed " result
    if packed > 41000 display "packed > 41000" end-if
    stop run.
