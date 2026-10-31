identification division.
program-id. lock-probe.
*> Tente un OPEN INPUT de chaque fichier pendant que lock-main le tient.
environment division.
input-output section.
file-control.
    select seq-file assign "seq.dat" organization sequential status fs1.
    select ls-file assign "ls.dat" organization line sequential status fs2.
    select rel-file assign "rel.dat" organization relative status fs3.
    select idx-file assign "idx.dat" organization indexed
        record key idx-key status fs4.
    select ex-file assign "ex.dat" organization sequential status fs5.
data division.
file section.
fd seq-file. 01 seq-rec pic x(4).
fd ls-file. 01 ls-rec pic x(4).
fd rel-file. 01 rel-rec pic x(4).
fd idx-file. 01 idx-rec. 05 idx-key pic x(4).
fd ex-file. 01 ex-rec pic x(4).
working-storage section.
01 fs1 pic xx. 01 fs2 pic xx. 01 fs3 pic xx. 01 fs4 pic xx. 01 fs5 pic xx.
procedure division.
    open input seq-file ls-file rel-file idx-file ex-file
    display "probe " fs1 " " fs2 " " fs3 " " fs4 " " fs5
    if fs1 = "00" close seq-file end-if
    if fs2 = "00" close ls-file end-if
    if fs3 = "00" close rel-file end-if
    if fs4 = "00" close idx-file end-if
    if fs5 = "00" close ex-file end-if
    stop run.
