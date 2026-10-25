*> An ENTRY name resolves only once its module is loaded: before any CALL
*> of ENTSUB, CALL "ENTALT" is EC-PROGRAM-NOT-FOUND.
identification division.
program-id. entfirst.
data division.
working-storage section.
01 text-arg pic x(6) value "TEXT".
01 count-arg pic 9(4) value 1.
procedure division.
    call "ENTALT" using count-arg
        on exception display "ENTALT not found"
    end-call
    call "ENTSUB" using text-arg count-arg
    call "ENTALT" using count-arg
    display "[" count-arg "]"
    call "ENTALT" using count-arg
    stop run.
