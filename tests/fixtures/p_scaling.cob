identification division.
program-id. p-scaling.
data division.
working-storage section.
01 grp.
   05 t1 pic s99p value 990.
   05 t2 pic 9ppp value 7000.
   05 l1 pic pp99 value .0012.
   05 l2 pic svp9 value -.05.
   05 l3 pic sp(3)9 value .0003.
   05 tail pic x value "|".
01 raw redefines grp pic x(8).
01 w pic s9(6)v9(6).
01 e pic -9(7).9(6).
01 n pic s9(4)pp.
procedure division.
    display raw
    display t1 " " t2 " " l1 " " l2 " " l3
    move 995 to t1 display t1
    move -1234 to t1 display t1
    move 12345 to t2 display t2
    move .00987 to l1 display l1
    move 1.0098 to l1 display l1
    move t1 to w display w
    move l1 to w display w
    move l3 to e display e
    move t2 to e display e
    add 15 to t1 display t1
    compute t1 rounded = 456 display t1
    compute t1 rounded = -455 display t1
    compute l2 rounded = .049 display l2
    compute l2 = .049 display l2
    compute t2 = 99999 on size error display "size t2" end-compute display t2
    compute t2 = 9999 on size error display "size t2b" end-compute display t2
    if t1 = -460 display "eq -460" end-if
    if l1 < .0013 display "lt" end-if
    multiply l3 by 1000000 giving w display w
    compute n = 345678 display n
    add 15 to n display n
    add 150 to n display n
    subtract 199 from n display n
    add t2 to n display n
    add 5 to t2 display t2
    add .0001 to l1 display l1
    subtract 1 from l3 on size error display "size l3" end-subtract display l3
    divide 7 into n display n
    display raw
    stop run.
