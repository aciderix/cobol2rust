*> Called by return_code.cob: its RETURN-CODE starts at zero at each CALL.
identification division.
program-id. RCSUB.
data division.
working-storage section.
01 calls pic 9 value 0.
procedure division.
    add 1 to calls
    display "sub initial [" return-code "] call " calls
    compute return-code = 7 * calls
    goback.
