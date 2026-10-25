identification division.
program-id. figurative-numeric.
data division.
working-storage section.
01 z pic 9 value zero.
01 n pic 999 value 121.
01 m pic 99v9 value 12.1.
procedure division.
    if quotes not = z display "1 yes" else display "1 no".
    if all zeroes = z display "2 yes" else display "2 no".
    if high-value > n display "3 yes" else display "3 no".
    if n = all "12" display "4 yes" else display "4 no".
    if n < all "2" display "5 yes" else display "5 no".
    if m = all "121" display "6 yes" else display "6 no".
    if low-values < n display "7 yes" else display "7 no".
    if n not = all "1" display "8 yes" else display "8 no".
    if n = all "13" display "9 yes" else display "9 no".
    if n > all "2" display "10 yes" else display "10 no".
    if m = high-value display "11 yes" else display "11 no".
    stop run.
