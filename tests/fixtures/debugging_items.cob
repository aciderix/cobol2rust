identification division.
program-id. debugging-items.
environment division.
configuration section.
source-computer. linux with debugging mode.
input-output section.
file-control.
    select out-file assign to "ITEMS.TXT".
data division.
file section.
fd out-file.
01 out-rec pic x(12).
working-storage section.
01 counter pic 99 value 0.
01 sel pic 9 value 2.
01 n pic 99.
01 m pic 99.
01 total pic 999 value 0.
01 spare pic 99 value 0.
01 grp.
    02 tab occurs 3 indexed by i.
        03 cell pic x occurs 2 indexed by j.
01 qa.
    02 leaf pic xx.
01 qb.
    02 leaf pic xx.
procedure division.
declaratives.
watch-items section.
    use for debugging on all references of n
                         m
                         all sel
                         cell
                         leaf of qb
                         all out-rec.
watch-1.
    add 1 to counter.
    display "dbg " debug-line " [" debug-name "] [" debug-contents(1:6)
            "] [" debug-item(39:17) "]".
end declaratives.
main section.
start-here.
    display "start".
    move 5 to n.
    move n to spare.
    move spare to m.
    add n n n to total.
    add 1 to m.
    if n = 5
        display "branch"
        move 1 to spare
    end-if.
    perform varying n from 1 by 2 until n > 4
        display "loop " n
    end-perform.
    perform varying m from 1 by 1 until m > 2
            after n from 3 by 1 until n > 4
        continue
    end-perform.
    perform until m > 4
        add 1 to spare
        move 9 to m
    end-perform.
    go to p1 p2 p3 depending on sel.
p1.
    display "p1".
p2.
    display "p2".
    set i to 2.
    set j to 1.
    move "Z" to cell (i, j).
    move "QQ" to leaf of qb.
    move "AA" to leaf of qa.
    open output out-file.
    write out-rec from "RECORD-ONE".
    move "SECOND" to out-rec.
    write out-rec.
    close out-file.
p3.
    display "counter " counter.
    stop run.
