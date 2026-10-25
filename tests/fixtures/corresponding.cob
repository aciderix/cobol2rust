identification division.
program-id. corresponding.
data division.
working-storage section.
01 src.
   05 a pic 99 value 12.
   05 b pic x(3) value "XYZ".
   05 sub.
      10 c pic 9 value 7.
      10 d pic x value "D".
   05 filler pic x value "F".
   05 e pic 9(3) value 456.
   05 t pic 9 occurs 2 value 1.
   05 g pic 99 value 34.
01 dst.
   05 e pic 9(2).
   05 sub.
      10 d pic x(2).
      10 c pic 99.
   05 b pic x(5).
   05 filler pic x value "-".
   05 a pic 999.
   05 t pic 9 occurs 2.
   05 g.
      10 g1 pic x.
      10 g2 pic x.
01 tot.
   05 a pic 9(3) value 100.
   05 sub.
      10 c pic 9 value 5.
   05 e pic 99 value 99.
   05 b pic 9 value 1.
procedure division.
    move all "*" to dst
    move corresponding src to dst
    display dst
    add corr src to tot
    display tot
    add corr src to tot on size error display "size" not on size error display "fine" end-add
    display tot
    subtract corresponding src from tot
    display tot
    stop run.
