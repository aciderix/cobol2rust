*> STOP RUN with a status (stop_returning): RETURNING or GIVING x, then
*> cob_stop_run of the integer part; Z"..." literals end with a NUL byte.
identification division.
program-id. stop-status.
data division.
working-storage section.
01 code-value pic 9v9 value 7.9.
01 zero-ended pic x(4) value z"abc".
procedure division.
    display "[" zero-ended "]" z"ok"
    move 5 to return-code
    stop run returning code-value.
