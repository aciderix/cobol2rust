identification division.
program-id. sibling-main.
data division.
working-storage section.
01 total pic 9(4) value 0.
01 target pic x(12) value "SIBLING-TWO".
procedure division.
    call "SIBLING-ONE" using total
    call "SIBLING-ONE" using total
    display "after two calls " total
    cancel "SIBLING-ONE"
    call "SIBLING-ONE" using total
    display "after cancel " total
    call target
    stop run.
end program sibling-main.
identification division.
program-id. SIBLING-ONE.
data division.
working-storage section.
01 calls pic 99 value 0.
linkage section.
01 l-total pic 9(4).
procedure division using l-total.
    add 1 to calls
    compute l-total = l-total + calls * 10
    display "one " calls
    goback.
end program SIBLING-ONE.
identification division.
program-id. SIBLING-TWO.
procedure division.
    display "two"
    exit program.
end program SIBLING-TWO.
