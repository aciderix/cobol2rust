identification division.
program-id. constant-lengths.
*> cb_build_const_length, cb_build_const_start, cb_build_const_next.
environment division.
input-output section.
file-control.
    select f assign "f.dat".
data division.
file section.
fd f.
01 frec.
   05 fa pic x(3).
   05 fb pic s9(5) comp-3.
      78 after-fb value next.
   05 fc pic x(2) occurs 4.
      78 after-fc value next.
   05 fd-item pic 9(4) comp.
01 frec2 pic x(30).
   78 after-frec2 value next.
01 frec3 pic x(6).
   78 len-frec3 value length of frec3.
   78 after-frec3 value next.
78 start-fb value start of fb.
78 start-fd value start of fd-item.
working-storage section.
01 rec.
   05 cell pic x(3) occurs 5.
   05 tail pic x.
   05 tail-r redefines tail pic x.
01 small pic x(4).
01 big redefines small pic x(9).
01 bin pic s9(9) comp.
78 len-cell value length of cell.
78 len-rec value length of rec.
78 len-tail-r value length tail-r.
78 len-small value length of small.
01 len-bin constant as byte-length of bin.
78 len-lit value length of "abcde".
01 len-usage constant as length of binary-double + length of pointer
    + byte-length float-long + length of comp-1 + length "xy" + length of float-decimal-34.
01 expr constant as length of rec * 2 + start-fb.
procedure division.
    display len-cell " " function length (cell (1)) " " len-rec
    display len-tail-r " " len-small " " len-bin " " len-lit " " len-usage
    display after-fb " " after-fc " " after-frec2 " " start-fb " " start-fd
    display expr " " len-frec3 " " after-frec3
    stop run.
