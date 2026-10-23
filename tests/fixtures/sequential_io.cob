*> SEQUENTIAL OPEN I-O and REWRITE statuses: 35, 05 (created), 43, 48, 49.
identification division. program-id. sequential-io.
environment division. input-output section. file-control.
    select f assign to "seq.dat" organization sequential file status fs.
    select g assign to "missing.dat" organization sequential file status gs.
    select optional h assign to "optional.dat" organization sequential file status hs.
data division. file section.
fd f. 01 rec pic x(3).
fd g. 01 grec pic x(3).
fd h. 01 hrec pic x(3).
working-storage section.
01 fs pic xx. 01 gs pic xx. 01 hs pic xx.
procedure division.
    open output f write rec from "AAA" write rec from "BBB" write rec from "CCC" close f
    open i-o g display "G-IO " gs
    open i-o h display "H-IO " hs read h display "H-READ " hs close h display "H-CLOSE " hs
    open i-o f display "OPEN " fs
    rewrite rec from "ZZZ" display "RW-NOREAD " fs
    read f display "READ1 " fs " " rec
    rewrite rec from "aaa" display "RW1 " fs
    rewrite rec from "xxx" display "RW-TWICE " fs
    read f display "READ2 " fs " " rec
    move "bbb" to rec rewrite rec display "RW2 " fs
    write rec display "WRITE-IO " fs
    read f display "READ3 " fs " " rec
    read f display "READ4 " fs
    rewrite rec from "eee" display "RW-EOF " fs
    close f
    open input f rewrite rec display "RW-INPUT " fs close f
    open input f read f display "R " rec read f display "R " rec read f display "R " rec close f
    stop run.
