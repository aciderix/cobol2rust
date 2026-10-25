*> USE AFTER ERROR procedures: by file, by OPEN mode, and resumption.
identification division.
program-id. declaratives.
environment division.
input-output section.
file-control.
    select data-file assign to "data.txt" organization line sequential
        file status data-status.
    select missing-file assign to "missing.txt" organization line sequential
        file status missing-status.
    select bare-file assign to "bare.txt" organization line sequential.
data division.
file section.
fd data-file. 01 data-rec pic x(4).
fd missing-file. 01 missing-rec pic x(4).
fd bare-file. 01 bare-rec pic x(4).
working-storage section.
01 data-status pic xx.
01 missing-status pic xx.
01 calls pic 99 value 0.
procedure division.
declaratives.
data-errors section.
    use after standard error procedure on data-file.
data-handler.
    add 1 to calls
    display "DATA-USE " data-status " " calls
    if data-status = "46" go to data-done.
    display "DATA-NOT-46".
data-done.
    exit.
input-errors section.
    use after exception procedure input.
input-handler.
    add 1 to calls
    display "INPUT-USE " missing-status " " calls.
output-errors section.
    use after standard exception procedure on output.
output-handler.
    add 1 to calls
    display "OUTPUT-USE " calls.
end declaratives.
main section.
start-here.
    open output data-file
    write data-rec from "AB"
    close data-file
    open input data-file
    read data-file display "READ " data-status " " data-rec
    read data-file display "AFTER-EOF " data-status
    read data-file at end display "AT-END " data-status
        not at end display "NOT-AT-END" end-read
    display "AFTER-46 " data-status
    open output data-file
    display "AFTER-41 " data-status
    close data-file
    close data-file
    display "AFTER-42 " data-status
    open input missing-file data-file
    display "MULTI " missing-status " " data-status
    close data-file
    open output bare-file
    open output bare-file
    display "BARE-41"
    close bare-file
    *> A 41 keeps the previous OPEN mode: INPUT, not the OUTPUT attempted.
    open input bare-file
    open output bare-file
    display "MODE-KEPT"
    close bare-file
    open extend missing-file
    display "EXTEND " missing-status
    display "CALLS " calls
    stop run.
