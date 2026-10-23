identification division.
program-id. comparison-folding.
data division.
working-storage section.
01 bytes-a pic x(7).
01 edited-a redefines bytes-a pic -9(3).99.
01 n pic s99 value -5.
01 u pic 99 value 7.
01 d pic 9v9 value 1.5.
01 e pic zz9.99.
01 x2 pic xx value "AB".
01 n2 pic s99v99 value 12.3.
procedure division.
    move "1234567" to bytes-a
    if edited-a = "1234567" display "c1 true" else display "c1 false" end-if
    if edited-a <> "1234567" display "c2 true" else display "c2 false" end-if
    if n > -100 display "c3 true" else display "c3 false" end-if
    if n < -100 display "c4 true" else display "c4 false" end-if
    if u >= 100 display "c5 true" else display "c5 false" end-if
    if -100 < n display "c6 true" else display "c6 false" end-if
    if 100 > u display "c7 true" else display "c7 false" end-if
    if d = 1.55 display "c8 true" else display "c8 false" end-if
    if d < 1.55 display "c9 true" else display "c9 false" end-if
    if d = 1.50 display "c10 true" else display "c10 false" end-if
    if x2 = "ABC" display "c11 true" else display "c11 false" end-if
    if u = 007 display "c12 true" else display "c12 false" end-if
    if u > 0099 display "c13 true" else display "c13 false" end-if
    if n2 = "1230" display "c18 true" else display "c18 false" end-if
    if "1230" = n2 display "c19 true" else display "c19 false" end-if
    move 12.5 to e
    if e = " 12.50" display "c14 true" else display "c14 false" end-if
    if e = 1250 display "c15 true" else display "c15 false" end-if
    if e = 123456 display "c16 true" else display "c16 false" end-if
    if e > "1" display "c17 true" else display "c17 false" end-if
    evaluate n
        when 100 display "e1 100"
        when -5 display "e1 -5"
        when other display "e1 other"
    end-evaluate
    evaluate u
        when 123 display "e2 123"
        when other display "e2 other"
    end-evaluate
    stop run.
