identification division.
program-id. lock-main.
*> Verrous fcntl de cob_file_open : lecture pour INPUT, écriture sinon ;
*> UNLOCK les relâche sauf en mode exclusif ; INDEXED sans DB_HOME : aucun.
environment division.
input-output section.
file-control.
    select seq-file assign "seq.dat" organization sequential status fs1.
    select ls-file assign "ls.dat" organization line sequential status fs2.
    select rel-file assign "rel.dat" organization relative status fs3
        lock mode is manual with lock on multiple records.
    select idx-file assign "idx.dat" organization indexed
        record key idx-key status fs4 lock mode automatic.
    select ex-file assign "ex.dat" organization sequential status fs5
        lock mode is exclusive.
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
    open output idx-file
    write idx-rec from "i001"
    close idx-file
    open output seq-file ls-file rel-file ex-file
    open i-o idx-file
    write seq-rec from "s001"
    write ls-rec from "l001"
    write rel-rec from "r001"
    write idx-rec from "i002"
    write ex-rec from "e001" with no lock
    display "writers"
    call "SYSTEM" using "./lock-probe"
    unlock seq-file
    unlock rel-file records
    unlock ex-file
    display "unlocked " fs1 " " fs3 " " fs5
    call "SYSTEM" using "./lock-probe"
    close seq-file ls-file rel-file idx-file ex-file
    open input seq-file
    open extend ls-file
    open i-o rel-file with lock
    open input sharing with no other ex-file
    display "readers"
    call "SYSTEM" using "./lock-probe"
    unlock rel-file
    unlock ex-file
    unlock idx-file
    display "unlock closed " fs4
    call "SYSTEM" using "./lock-probe"
    read seq-file with no lock end-read
    read rel-file next with kept lock end-read
    display "read " fs1 " " seq-rec " " fs3 " " rel-rec
    close seq-file ls-file rel-file ex-file
    call "SYSTEM" using "./lock-probe"
    stop run.
