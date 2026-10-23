*> Variable-length records: DEPENDING ON, implied by 01 sizes, 44, READ INTO size, RELATIVE sizes.
identification division. program-id. variable-records.
environment division. input-output section. file-control.
    select f assign to "var.dat" organization sequential file status fs.
    select g assign to "nodep.dat" organization sequential file status gs.
    select r assign to "rel.dat" organization relative access dynamic relative key rk file status rs.
data division. file section.
fd f record is varying in size from 3 to 10 characters depending on len.
01 short-rec pic x(5).
01 long-rec pic x(8).
fd g.
01 g-short pic x(4).
01 g-long pic x(9).
fd r record varying from 2 to 6 depending on rlen.
01 r-rec pic x(6).
working-storage section.
01 fs pic xx. 01 gs pic xx. 01 rs pic xx. 01 rk pic 9.
01 len pic 99. 01 rlen pic 9.
01 target pic x(12).
procedure division.
    open output f
    move 4 to len write short-rec from "ABCDE" display "W4 " fs
    move 7 to len write long-rec from "1234567" display "W7 " fs
    move 9 to len write short-rec from "VWXYZ" display "W9-SHORT " fs
    move 2 to len write short-rec display "W2 " fs
    move 11 to len write long-rec display "W11 " fs
    close f
    open input f
    move all "*" to long-rec
    read f display "R1 " fs " " len " [" long-rec "]"
    read f display "R2 " fs " " len " [" long-rec "]"
    read f into target display "R3 " fs " " len " [" long-rec "] [" target "]"
    read f display "R4 " fs " " len
    close f
    open output g
    write g-short from "SSSS" write g-long from "LLLLLLLLL" write g-short from "TT" display "GW " gs
    close g
    open input g
    move all "#" to g-long
    read g display "GR1 " gs " [" g-long "]"
    read g display "GR2 " gs " [" g-long "]"
    read g into target display "GR3 " gs " [" g-long "] [" target "]"
    close g
    open output r
    move 1 to rk move 3 to rlen write r-rec from "abcdef" display "RW1 " rs
    move 2 to rk move 6 to rlen write r-rec from "ghijkl" display "RW2 " rs
    move 3 to rk move 7 to rlen write r-rec from "mnopqr" display "RW3 " rs
    close r
    open input r
    move 1 to rk read r display "RR1 " rs " " rlen " [" r-rec "]"
    read r next display "RR2 " rs " " rlen " [" r-rec "]"
    close r
    stop run.
