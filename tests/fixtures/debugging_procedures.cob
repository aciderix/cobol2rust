identification division.
program-id. debugging-procedures.
*> USE FOR DEBUGGING on procedures, ALL PROCEDURES-like series, a file and
*> SORT procedures, as cobc 3.2 generates them: DEBUG-LINE of the last
*> statement begun, DEBUG-NAME of the label, DEBUG-CONTENTS "START PROGRAM",
*> "PERFORM LOOP", "FALL THROUGH", the ALTER target, a READ record, etc.
environment division.
configuration section.
source-computer. this-computer with debugging mode.
input-output section.
file-control.
    select data-file assign to "DBGDATA" organization line sequential.
    select work-file assign to "DBGWORK".
data division.
file section.
fd data-file.
01 data-rec pic x(12).
sd work-file.
01 work-rec pic x(12).
working-storage section.
01 n pic 9 value 0.
procedure division.
declaratives.
trace-procedures section.
    use for debugging on step-1 step-2 later-part step-3 sort-in sort-out.
show-trace.
    display "[" debug-line "|" debug-name "|" debug-contents "]".
trace-file section.
    use for debugging on data-file.
show-file.
    display "<" debug-name "|" debug-contents ">".
end declaratives.
main-part section.
begin-here.
    perform step-1.
    perform step-1 2 times.
    go to step-2.
step-1.
    add 1 to n.
step-2.
    alter step-3 to proceed to step-4.
    open output data-file.
    move "first record" to data-rec.
    write data-rec.
    close data-file.
    open input data-file.
    read data-file.
    close data-file.
    sort work-file on ascending key work-rec
        input procedure sort-in
        output procedure sort-out.
later-part section.
step-3.
    go to step-5.
step-4.
    display "step-4".
step-5.
    stop run.
sort-in.
    move "zz" to work-rec.
    release work-rec.
sort-out.
    return work-file at end continue end-return.
