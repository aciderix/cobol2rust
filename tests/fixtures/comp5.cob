*> COMP-5 and BINARY-CHAR/SHORT/LONG/DOUBLE (COB_FLAG_REAL_BINARY): storage
*> bounded by the binary size, not the PICTURE; cob_print_realbin display.
identification division.
program-id. comp5.
data division.
working-storage section.
01 s4 pic s9(4) comp-5 value 30000.
01 u4 pic 9(4) comp-5 value 9999.
01 s9 pic s9(9) comp-5 value 2147483647.
01 u2 pic 99 comp-5.
01 d2 pic s9(3)v99 comp-5 value 123.45.
01 s18 pic s9(18) computational-5.
01 bc binary-char.
01 bcu binary-char unsigned.
01 bs binary-short signed value -2.
01 bl binary-long.
01 bd binary-double unsigned.
01 g.
   02 gb pic s9(4) comp-5 value 258.
   02 gx pic x value "z".
01 txt pic x(8).
01 dsp pic 9(4).
procedure division.
    display "s4 " s4 " u4 " u4 " s9 " s9 " d2 " d2 " u2 " u2
    display "bc " bc " bcu " bcu " bs " bs " bl " bl " bd " bd
    move 123456 to s4  display "move 123456 to s9(4): " s4
    move 65535 to u4   display "move 65535 to 9(4): " u4
    move 65536 to u4   display "move 65536 to 9(4): " u4
    move 255 to u2     display "move 255 to 99: " u2
    move 300 to u2     display "move 300 to 99: " u2
    move -5 to u4      display "move -5 to unsigned: " u4
    move 30000 to s4
    add 10000 to s4    display "add 10000 no size error: " s4
    move 30000 to s4
    add 10000 to s4 on size error display "size error s4 " s4 not on size error display "no size error s4 " s4 end-add
    move 9999 to s4
    add 1 to s4 on size error display "size error 10000 " s4 not on size error display "ok 10000 " s4 end-add
    move -32767 to s4
    subtract 1 from s4 on size error display "size error -32768 " s4 end-subtract
    compute s9 = 2147483647 + 1 on size error display "size error s9 " s9 end-compute
    compute s9 = 9999999999   display "compute 9999999999: " s9
    compute d2 rounded = 1.005 * 3 display "rounded d2 " d2
    move s4 to txt     display "to text [" txt "]"
    move 40000 to u4
    move u4 to dsp     display "to display " dsp
    move u4 to s9      display "to s9 " s9
    move 127 to bc
    add 1 to bc        display "bc wraps " bc
    move 200 to bcu    display "bcu " bcu
    multiply 2 by bcu  display "bcu * 2 " bcu
    move -1 to bd      display "bd " bd
    move 1234567890123 to s18 display "s18 " s18
    if s4 > 5000 display "compare ok" end-if
    if u4 = 40000 display "u4 = 40000" end-if
    initialize s9      display "initialized " s9
    move 4 to bl
    compute bl = bl * bl - 20 display "bl " bl
    stop run.
