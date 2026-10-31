identification division.
program-id. small-constructs.
*> UNSTRING d'un littéral et d'une FUNCTION, CALL STATIC, INSPECT ... NULL,
*> ACCEPT OMITTED.
data division.
working-storage section.
01 parts.
   05 part pic x(6) occurs 3.
01 x pic x(5) value x"0041004200".
01 n pic 99 value 0.
procedure division.
    unstring "ab,cd,ef" delimited by "," into part (1) part (2) part (3)
        on overflow display "overflow" end-display
        not on overflow display "[" parts "]" end-display
    end-unstring
    unstring function upper-case ("gh;ij") delimited by ";" into part (1) part (2)
    display "[" parts "]"
    call static "callee" on exception display "never" end-call
    call static "callee" not on exception display "after static" end-display end-call
    inspect x tallying n for all null
    inspect x converting null to "."
    display n " [" x "]"
    accept omitted
    accept omitted not on exception display "omitted" end-display end-accept
    display "end"
    stop run.
end program small-constructs.
identification division.
program-id. callee.
procedure division.
    display "in callee"
    goback.
end program callee.
