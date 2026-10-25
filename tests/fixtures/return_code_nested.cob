*> A contained program shares its container's RETURN-CODE (GLOBAL); the
*> main program's GOBACK makes it the exit status.
identification division.
program-id. rcouter.
procedure division.
    move 3 to return-code
    call "rcinner"
    display "after inner [" return-code "]"
    goback.
identification division.
program-id. rcinner.
procedure division.
    display "inner sees [" return-code "]"
    add 20 to return-code
    goback.
end program rcinner.
end program rcouter.
