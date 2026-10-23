identification division.
program-id. edited-size-error.
data division.
working-storage section.
01 e1 pic zz9.99.
01 e2 pic -9(3).
01 x3 pic x(3).
01 x6 pic x(6).
01 a pic s9pp value 200.
01 a2 pic 99ppp value 12000.
01 q pic x(4) value quote.
01 g.
   05 g1 pic xx value quotes.
   05 g2 pic x.
procedure division.
    move 12.5 to e1
    compute e1 = 999.994 on size error display "size1" not on size error display "ok1" end-compute
    display e1
    compute e1 rounded = 999.995 on size error display "size2" not on size error display "ok2" end-compute
    display e1
    compute e2 = -999 on size error display "size4" end-compute display e2
    compute e2 = -1000 on size error display "size5" end-compute display e2
    move a to x3 x6 display "[" x3 "][" x6 "]"
    move a2 to x3 x6 display "[" x3 "][" x6 "]"
    display "[" q "][" g "]"
    move quote to x6 display "[" x6 "]"
    move quotes to g display "[" g "]"
    if e1 = "999.99" display "eq" end-if
    if e1 > "100" display "gt" end-if
    stop run.
