*> RETURN-CODE: a BINARY-LONG register per program, cleared at each CALL,
*> set from the callee's return value, and the process exit status.
identification division.
program-id. rcmain.
data division.
working-storage section.
01 x pic s9(4) value -12.
procedure division.
    display "initial [" return-code "]"
    move 4 to return-code
    display "after move [" return-code "]"
    add 1 to return-code
    if return-code = 5 display "is five" end-if
    move x to return-code
    display "negative [" return-code "]"
    call "RCSUB"
    display "after call [" return-code "]"
    call "RCSUB"
    display "after second call [" return-code "]"
    cancel "RCSUB"
    call "RCSUB"
    display "after cancel and call [" return-code "]"
    move 300 to return-code
    stop run.
