identification division.
program-id. library-main.
data division.
working-storage section.
01 a        pic x(8) value "abcd    ".
01 r        pic s9(9) comp-5.
01 n        pic 9(4).
01 word     pic x(10) value "   ab     ".
01 raw-bytes    pic x(6) value x"41000142FF43".
01 rep-char      pic x value "#".
01 caller   pic x(16).
01 cmd      pic x(30) value "echo child; exit 3".
procedure division.
    move 7 to return-code
    call "library-sub" using function trim(a) "12345678" returning r
    display "returning " r " " return-code
    call "library-sub" using by content function upper-case(a) a giving n
    display "giving " n " " return-code
    call "library-sub" using "wxyz" omitted returning omitted
    display "omitted " return-code
    call "C$CALLEDBY" using caller
    display "main calledby " return-code " [" caller "]"
    call "C$JUSTIFY" using word "R" display "[" word "]"
    call "C$JUSTIFY" using word "L" display "[" word "]"
    call "C$JUSTIFY" using word "C" display "[" word "]"
    call "C$JUSTIFY" using word display "[" word "]"
    call "C$PRINTABLE" using raw-bytes display function hex-of(raw-bytes)
    move x"41000142FF43" to raw-bytes
    call "C$PRINTABLE" using raw-bytes rep-char display function hex-of(raw-bytes)
    call "C$SLEEP" using 0 display "sleep " return-code
    display "before"
    call "SYSTEM" using cmd display "system " return-code
    call "SYSTEM" using "x" display "one " return-code
    move 0 to return-code
    stop run.
