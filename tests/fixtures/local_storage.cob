*> LOCAL-STORAGE: storage allocated and initialized at each CALL, unlike
*> WORKING-STORAGE, kept between CALLs.
identification division.
program-id. lsmain.
procedure division.
    call "LSSUB"
    call "LSSUB"
    call "LSSUB"
    stop run.
