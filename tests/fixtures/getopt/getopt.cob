identification division.
program-id. getopt-case.
*> cob_sys_getopt_long_long: options courtes et longues, abréviations,
*> ambiguïtés, permutation d'argv, ordres + et -, ':' en tête, -W, flag.
data division.
working-storage section.
01 lo.
   05 optionrecord occurs 7 times.
      10 oname        pic x(25).
      10 has-value    pic 9.
      10 valpoint     usage pointer value null.
      10 val          pic x(4).
01 so          pic x(20).
01 longind     pic 99 value 0.
01 long-only   pic 9 value 0.
01 return-char pic x(4).
01 opt-val     pic x(6).
01 flag-val    pic x(4) value "----".
01 ret-disp    pic -999.
01 counter     pic 99 value 0.
procedure division.
    accept so
    accept long-only
    move "version" to oname(1) move 0 to has-value(1) move "v" to val(1)
    move "verbose" to oname(2) move 0 to has-value(2) move "V" to val(2)
    move "value"   to oname(3) move 1 to has-value(3) move "x" to val(3)
    move "opt"     to oname(4) move 2 to has-value(4) move "o" to val(4)
    move "flag"    to oname(5) move 0 to has-value(5) move "1" to val(5)
    set valpoint(5) to address of flag-val
    move "flag2"   to oname(6) move 0 to has-value(6) move "1" to val(6)
    set valpoint(6) to address of flag-val
    move "exactly-twenty-five-chars" to oname(7) move 0 to has-value(7)
    move x"01020304" to val(7)
    perform with test after varying counter from 1 by 1
            until return-code = -1 or counter > 30
        move spaces to opt-val
        call "CBL_GC_GETOPT" using by reference so lo longind
             by value long-only by reference return-char opt-val
        end-call
        move return-code to ret-disp
        display counter " " ret-disp " [" return-char "] " longind
                " [" opt-val "] [" flag-val "]"
    end-perform
    display "[" oname(1) "][" oname(4) "][" oname(7) "]"
    move 0 to return-code
    stop run.
