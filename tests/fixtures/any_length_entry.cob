identification division.
program-id. any-length-entry-main.
data division.
working-storage section.
01 six pic x(6) value "ABCDEF".
01 three pic x(3) value "xyz".
01 four pic x(4) value "1234".
procedure division.
    call "ANY-ENTRY" using omitted omitted
    call "SECOND-ONLY" using four
    call "ANY-ENTRY" using six three
    call "SECOND-ONLY" using four
    call "SWAP-ANY" using three six
    call "ANY-ENTRY" using omitted omitted
    cancel "ANY-ENTRY"
    call "ANY-ENTRY" using omitted omitted
    call "ANY-ENTRY" using four three
    call "INITIAL-ANY" using omitted
    call "INITIAL-ANY" using six
    call "INITIAL-ANY" using omitted
    call "INITIAL-ANY" using three
    cancel "INITIAL-ANY"
    call "INITIAL-ANY" using omitted
    goback.
end program any-length-entry-main.

identification division.
program-id. ANY-ENTRY.
data division.
linkage section.
01 first-arg pic x any length.
01 second-arg pic x any length.
procedure division using first-arg second-arg.
    display "main|" length of first-arg "|" length of second-arg "|"
    goback.
entry "SWAP-ANY" using second-arg first-arg.
    display "swap|" length of first-arg "|" length of second-arg "|"
    goback.
entry "SECOND-ONLY" using second-arg.
    display "second|" length of first-arg "|" length of second-arg "|"
    goback.
end program ANY-ENTRY.

identification division.
program-id. INITIAL-ANY is initial.
data division.
linkage section.
01 arg pic x any length.
procedure division using arg.
    display "initial|" length of arg "|"
    goback.
end program INITIAL-ANY.
