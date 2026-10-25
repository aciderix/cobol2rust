identification division.
program-id. abbreviated-conditions.
data division.
working-storage section.
01 a pic s99 value 13.
01 b pic s99 value -4.
01 z pic 9 value 0.
01 t pic x(4) value "ab C".
01 u pic x(3) value "ABC".
01 l pic x(3) value "abc".
01 d pic x(3) value "a1c".
01 k pic 9 value 4.
   88 low-k value 0 thru 4.
procedure division.
    if a not equal to 12 and greater than 10 display "1 yes" else display "1 no".
    if a = 12 or 13 display "2 yes" else display "2 no".
    if a not = 12 and 13 display "3 yes" else display "3 no".
    if a > 20 or < 15 display "4 yes" else display "4 no".
    if a = 1 or not 2 display "5 yes" else display "5 no".
    if a > b and not < 5 display "6 yes" else display "6 no".
    if not a = 13 or b = -4 display "7 yes" else display "7 no".
    if not (a = 13 and b = 1) display "8 yes" else display "8 no".
    if a is positive and b is negative and z is zero display "9 yes" else display "9 no".
    if a is not positive or b not negative or z not zero display "10 yes" else display "10 no".
    if t alphabetic display "11 yes" else display "11 no".
    if u alphabetic-upper and l alphabetic-lower display "12 yes" else display "12 no".
    if d alphabetic or d alphabetic-lower display "13 yes" else display "13 no".
    if a + 1 > b * 3 and a - 13 = z display "14 yes" else display "14 no".
    if a = 13 and b = 1 or z = 0 display "15 yes" else display "15 no".
    if a = 1 or b = -4 and z = 1 display "16 yes" else display "16 no".
    if low-k and a > 10 display "17 yes" else display "17 no".
    if a > 10 and (b = 1 or 2 or -4) display "18 yes" else display "18 no".
    if a = 10 or 11 or 12 or 13 display "19 yes" else display "19 no".
    if a greater than or equal to 13 and less than or equal 13 display "20 yes" else display "20 no".
    if a >= 14 or <= 12 display "21 yes" else display "21 no".
    if z = zero and not zero = 1 display "22 yes" else display "22 no".
    if a is not greater 13 and is not less 13 display "23 yes" else display "23 no".
    perform until a < 10 or = 20
        subtract 1 from a
    end-perform
    display a
    stop run.
