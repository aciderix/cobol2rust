*> ENTRY 'name' USING: a second entry point of a called program. Its
*> execution starts at the ENTRY statement, which is only a label when the
*> program runs through it; its USING items are bound for that CALL.
identification division.
program-id. entmain.
data division.
working-storage section.
01 first-arg pic x(6) value "FIRST".
01 second-arg pic 9(4) value 12.
procedure division.
    call "ENTSUB" using first-arg second-arg
    display "after main entry [" first-arg "] [" second-arg "]"
    call "ENTALT" using second-arg
    display "after alternate entry [" second-arg "]"
    call "ENTSUB" using first-arg second-arg
    display "after main entry again [" first-arg "] [" second-arg "]"
    stop run.
