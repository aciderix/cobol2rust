identification division.
program-id. perform-backward-thru.
*> PERFORM a THRU b where b comes first: the PERFORM returns at the end
*> of b whenever control reaches it (cobc's perform_through exit check).
data division.
working-storage section.
01 trail pic x(20) value spaces.
01 pos pic 99 value 1.
01 rounds pic 9 value 0.
procedure division.
main-para.
    perform later-para thru early-para.
    display trail.
    stop run.
early-para.
    move "E" to trail(pos:1). add 1 to pos.
middle-para.
    move "M" to trail(pos:1). add 1 to pos.
    if rounds = 0
        add 1 to rounds
        go to early-para.
    display "fell beyond the range".
    stop run.
later-para.
    move "L" to trail(pos:1). add 1 to pos.
    go to early-para.
