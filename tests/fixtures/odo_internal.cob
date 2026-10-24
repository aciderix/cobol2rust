identification division.
program-id. odo-internal.
environment division.
input-output section.
file-control.
    select vfile assign to "VAR.DAT" organization sequential file status vs.
data division.
file section.
fd vfile record is varying.
01 v-rec.
   02 v-n pic 9.
   02 v-t pic x occurs 1 to 9 depending on v-n.
working-storage section.
01 vs pic xx.
01 a-rec.
   02 a-n pic 9.
   02 a-t pic x occurs 0 to 9 depending on a-n.
01 b-rec.
   02 b-n pic 9.
   02 b-t pic x occurs 0 to 9 depending on b-n.
01 c pic x(12).
01 i pic 99.
procedure division.
    move 5 to a-n. move "ABCDE" to a-rec(2:5).
    move 2 to b-n.
    move a-rec to b-rec.
    display "[" b-rec "] " b-n.
    move 9 to b-n display "[" b-rec "]".
    move 3 to b-n.
    move "7XYZWVUTSRQ" to b-rec.
    display "[" b-rec "] " b-n.
    move 9 to b-n display "[" b-rec "]".
    move b-rec to c. display "[" c "]".
    move 4 to a-n.
    move a-rec to c. display "[" c "]".
    open output vfile.
    perform varying i from 1 by 1 until i > 3
        move i to v-n
        move "abcdefghi" to v-rec(2:i)
        write v-rec
    end-perform.
    close vfile.
    open input vfile.
    move 1 to b-n.
    perform 3 times
        read vfile into b-rec
        display vs " [" b-rec "] " b-n
    end-perform.
    close vfile.
    stop run.
