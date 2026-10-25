identification division.
program-id. deediting.
data division.
working-storage section.
01 e1 pic -999.99.
01 e2 pic zz9.9cr.
01 e3 pic $$,$$9.99.
01 e4 pic 99pp.
01 e5 pic ***9.
01 n1 pic s9(4)v99.
01 n2 pic 999.
01 n3 pic s99v9 sign trailing separate.
01 n4 pic s9(5) comp-3.
01 n5 pic 9(6).
01 o1 pic +zz9.99.
procedure division.
    move -123.45 to e1
    move e1 to n1 n2 n3 n4 o1
    display n1 " " n2 " " n3 " " n4 " " o1
    move 42.5 to e2
    move e2 to n1 n2
    display e2 " " n1 " " n2
    move -7.3 to e2
    move e2 to n1 n3
    display e2 " " n1 " " n3
    move 1234.5 to e3
    move e3 to n1 n2
    display e3 " " n1 " " n2
    move 4500 to e4
    move e4 to n5 n1
    display e4 " " n5 " " n1
    move 12 to e5
    move e5 to n2
    display e5 " " n2
    stop run.
