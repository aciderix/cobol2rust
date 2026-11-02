identification division.
program-id. comp-x.
data division.
working-storage section.
01 a pic x comp-x value 200.
01 b pic xx comp-x value 65535.
01 c pic x(3) comp-x.
01 d pic 9(3) comp-x value 999.
01 e pic 9(5) comp-n value 12345.
01 f pic s9(4) comp-x value -1234.
01 h pic 99 comp-x value 99.
01 n pic 9(9).
01 r redefines n pic x(9).
01 g1.
   05 x1 pic 9(4) comp-x value 258.
   05 n1 pic 9(4) comp-n value 258.
   05 b1 pic 9(4) comp value 258.
   05 s1 pic s9(4) comp-x value -2.
01 a4 pic x(4).
01 t pic x(2) comp-x.
01 u pic 9(3) comp-x.
01 v pic s99 comp-n.
procedure division.
    display a " " b " " d " " e " " f " " h
    display function length(a) " " function length(b) " " function length(c) " " function length(d) " "
            function length(e) " " function length(f) " " function length(h)
    move 300 to a display a
    move 256 to b display b
    move 65536 to b display b
    add 1 to b display b
    move 16777215 to c display c
    add 1 to c on size error display "c size" end-add display c
    move 1000 to d display d
    compute d = 999 + 1 on size error display "d size" end-compute display d
    move a to n display n
    move 255 to a add 1 to a display a
    move 99 to h add 1 to h display h
    compute h = h + 200 display h
    move -5 to a display a
    display "x" c "x"
    move e to n display n
    display function hex-of(g1)
    move 65535 to t multiply 2 by t display t
    move 65535 to t multiply 2 by t on size error display "t size" end-multiply display t
    move 7 to u divide 2 into u display u
    move x1 to a4 display "[" a4 "]"
    if x1 = 258 display "eq" end-if
    if x1 > n1 display "gt" else display "le" end-if
    move 200 to v display v
    move -200 to v display v
    subtract 1 from u giving t display t
    initialize g1 display function hex-of(g1)
    stop run.
