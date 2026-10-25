identification division.
program-id. procedure-names.
*> cb_ref for labels: homonym paragraphs in different sections, an
*> unqualified name resolved inside its own section, IN/OF qualification
*> from outside, and all-digit procedure names.
data division.
working-storage section.
01 trail pic x(30) value spaces.
01 pos pic 99 value 1.
procedure division.
main-part section.
start-here.
    perform step of first-part.
    perform step in second-part.
    perform first-part.
    perform second-part.
    perform 100 thru 200.
    go to 300.
100.
    move "1" to trail(pos:1). add 1 to pos.
200.
    move "2" to trail(pos:1). add 1 to pos.
300.
    display trail.
    stop run.
first-part section.
entry-1.
    perform step.
    go to done.
step.
    move "a" to trail(pos:1). add 1 to pos.
done.
    exit.
second-part section.
entry-2.
    perform step.
    go to done of second-part.
step.
    move "b" to trail(pos:1). add 1 to pos.
done.
    exit.
