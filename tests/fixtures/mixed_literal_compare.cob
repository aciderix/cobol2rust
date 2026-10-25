identification division.
program-id. mixed-literal-compare.
data division.
working-storage section.
01 n2 pic 99 value 22.
01 d2 pic 9v9 value 2.2.
01 s2 pic s99 value 22.
01 c2 pic 99 comp value 22.
01 n3 pic 999 value 22.
01 sp pic 9(3)p value 1000.
01 t2 pic s99 value -22.
01 l2 pic s99 sign leading separate value -22.
01 r2 pic s99 sign trailing separate value -22.
01 p2 pic s99 value 22.
01 e2 pic s9v9 value -2.2.
01 n pic 999 value 12.
01 m pic 999 value 120.
01 w pic 999 value 12.
01 q pic s99v99 value 12.30.
procedure division.
    if n2 < "AA" display "1 lt" else display "1 ge" end-if.
    if d2 = "22" display "2 eq" else display "2 ne" end-if.
    if n2 = "2" display "3 eq" else display "3 ne" end-if.
    if n2 > "2" display "3b gt" else display "3b le" end-if.
    if s2 = "22" display "4 eq" else display "4 ne" end-if.
    if c2 = "22" display "5 eq" else display "5 ne" end-if.
    if n3 = "022" display "6 eq" else display "6 ne" end-if.
    if n3 = "22 " display "7 eq" else display "7 ne" end-if.
    if "AA" > n2 display "8 gt" else display "8 le" end-if.
    if d2 < "3" display "9 lt" else display "9 ge" end-if.
    if sp = "001" display "10 eq" else display "10 ne" end-if.
    if t2 = "22" display "b1 eq" else display "b1 ne" end-if.
    if t2 = "2r" display "b2 eq" else display "b2 ne" end-if.
    if l2 = "-22" display "b3 eq" else display "b3 ne" end-if.
    if l2 = "22" display "b4 eq" else display "b4 ne" end-if.
    if r2 = "22-" display "b5 eq" else display "b5 ne" end-if.
    if p2 = "22" display "b6 eq" else display "b6 ne" end-if.
    if d2 < "3" display "b7 lt" else display "b7 ge" end-if.
    if d2 = "AB" display "b8 eq" else display "b8 ne" end-if.
    if d2 < "2" display "b9 lt" else display "b9 ge" end-if.
    if e2 = "22" display "b10 eq" else display "b10 ne" end-if.
    if e2 > "21" display "b11 gt" else display "b11 le" end-if.
    if l2 < "-3" display "b12 lt" else display "b12 ge" end-if.
    if d2 = "2 " display "b13 eq" else display "b13 ne" end-if.
    display "b[" t2 "]".
    if n = "12" display "c1 eq" else display "c1 ne" end-if.
    if m = "12" display "c1b eq" else display "c1b ne" end-if.
    if m > "12" display "c1c gt" else display "c1c le" end-if.
    if "0012" = n display "c2 eq" else display "c2 ne" end-if.
    if "012" = n display "c2b eq" else display "c2b ne" end-if.
    if n = "12A" display "c3 eq" else display "c3 ne" end-if.
    if n < "12A" display "c3b lt" else display "c3b ge" end-if.
    evaluate w when "12" display "c4 when" when other display "c4 other" end-evaluate.
    evaluate w when "012" display "c4b when" when other display "c4b other" end-evaluate.
    if q = "1230" display "c5 eq" else display "c5 ne" end-if.
    if q = "123" display "c5b eq" else display "c5b ne" end-if.
    stop run.
