identification division.
program-id. recursive-main.
procedure division.
    move 5 to return-code
    call "recursive-first"
    display "main " return-code
    stop run.
end program recursive-main.
identification division.
program-id. recursive-first.
procedure division.
    move 7 to return-code
    call "recursive-second"
    display "first " return-code
    goback.
end program recursive-first.
identification division.
program-id. recursive-second.
procedure division.
    move 9 to return-code
    call "recursive-first"
        on exception display "exception " return-code " " function exception-status end-display
        not on exception display "no exception " return-code end-display
    end-call
    display "after " return-code " " function exception-location
    set last exception to off
    call "recursive-main" on exception display "main active " return-code end-display
    end-call
    display "second " function exception-status
    goback.
end program recursive-second.
