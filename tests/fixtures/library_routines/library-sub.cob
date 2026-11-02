identification division.
program-id. library-sub.
data division.
working-storage section.
01 narg     pic 9(4).
01 psize    pic 9(4).
01 caller   pic x(16).
linkage section.
01 l1       pic x(4).
01 l2       pic x(8).
procedure division using l1 l2.
    call "C$NARG" using narg
    display "narg " narg
    call "C$PARAMSIZE" using 1 giving psize
    display "size1 " psize
    call "C$PARAMSIZE" using 2 returning psize
    display "size2 " psize
    call "C$PARAMSIZE" using 3 returning psize
    display "size3 " psize
    call "C$CALLEDBY" using caller
    display "calledby " return-code " [" caller "]"
    move 42 to return-code
    goback.
