identification division.
program-id. perform-times-count.
*> PERFORM n TIMES as cobc emits it: for (n = cob_get_llint (x); n > 0; n--),
*> so a negative count runs zero times; an inline PERFORM alone runs once.
data division.
working-storage section.
01 neg pic s99 value -3.
01 tens pic 9p value 20.
01 trail pic x(40) value spaces.
01 pos pic 99 value 1.
procedure division.
    perform neg times
        move "N" to trail(pos:1) add 1 to pos
    end-perform.
    perform tens times
        move "T" to trail(pos:1) add 1 to pos
    end-perform.
    perform 2 times
        move "L" to trail(pos:1) add 1 to pos
    end-perform.
    perform
        move "O" to trail(pos:1) add 1 to pos
    end-perform.
    display trail.
    stop run.
