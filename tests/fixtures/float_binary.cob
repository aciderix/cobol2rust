identification division.
program-id. float-binary.
data division.
working-storage section.
01 s1 comp-1 value 123.456.
01 s2 comp-1.
01 d1 comp-2 value 0.1.
01 d2 comp-2.
01 big comp-2 value 1.0E300.
01 d6 comp-2.
01 n1 pic s9(5)v9(4).
01 n2 pic 9(3).
01 n6 pic 9 value 6.
01 e1 pic -zz9.99.
01 p1 pic s9(7)v99 comp-3.
01 b1 pic s9(9) comp.
01 cnt pic 999 value 0.
01 grp.
   05 g1 comp-1.
   05 g2 comp-2.
procedure division.
    display "values " s1 "|" d1 "|" s2 "|" d2
    move 1 to s2 display s2
    move -2.5 to s2 display s2
    move 1234567890 to s2 display s2
    move 0.000012345 to s2 display s2
    move 100000000 to d2 display d2
    move 12345678901234567 to d2 display d2
    move 0.0001 to d2 display d2
    move 0.00001 to d2 display d2
    move s1 to n1 display n1
    move d1 to n1 display n1
    move -123.456 to d2 move d2 to n1 display n1
    move s1 to n2 display n2
    move s1 to e1 display e1
    move s1 to d2 display d2
    move d1 to s2 display s2
    move 12345.678 to d2 move d2 to p1 display p1
    move -98765 to s2 move s2 to b1 display b1
    compute s2 = 1 / 3 display s2
    compute d2 = 2 / 3 display d2
    compute d2 = 1.0E7 / 2.1E0 / 3.1E0 - 5.0E-1 display d2
    add 0.1 to d1 display d1
    multiply 3 by d1 display d1
    divide 2 into s1 display s1
    subtract 1 from s1 display s1
    *> cob_cmp_float: relative tolerance of 1e-7
    if d1 = 0.6 display "tolerance eq" else display "tolerance ne" end-if
    if d1 * 1 = 0.6 display "folded eq" else display "folded ne" end-if
    if d1 * 2 = 1.2 display "decimal eq" else display "decimal ne" end-if
    compute d6 = 6.0000001
    if d6 = 6 display "llint eq" else display "llint ne" end-if
    if d6 = 6.0 display "float eq" else display "float ne" end-if
    if d6 = n6 display "right field eq" else display "right field ne" end-if
    if n6 = d6 display "left field eq" else display "left field ne" end-if
    if d6 > 6 and d6 < 7 display "between" end-if
    evaluate d6 when 6.0 display "when 6.0" when other display "other" end-evaluate
    *> overflow: SIZE ERROR keeps the receiver, otherwise inf then 0
    move 2 to s2
    perform until cnt > 140
       add 1 to cnt
       compute s2 = s2 * 2 on size error display "size " cnt " " s2 exit perform end-compute
    end-perform
    move 2 to s2
    perform 130 times compute s2 = s2 * 2 end-perform
    display "no size error " s2
    compute d2 = big * big on size error display "dsize " d2 not on size error display "dok " d2 end-compute
    compute d2 = big * big display "big " d2
    compute d2 = 1 / 0 on size error display "div0" end-compute
    compute d2 = -0.0 display d2
    initialize grp display g1 " " g2
    move 7 to g1 move g1 to g2 display g2
    compute s2 = 16777217 display s2
    compute d2 = 9007199254740993 display d2
    perform varying d2 from 1.0 by 0.5 until d2 > 3 display d2 " " no advancing end-perform
    display " "
    move high-value to g1 display g1
    stop run.
