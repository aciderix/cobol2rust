identification division.
program-id. sequential-records.
environment division.
input-output section.
file-control.
    select records-file assign to "records.bin" file status file-state.
data division.
file section.
fd records-file.
01 structured-record.
    05 amount-a pic s9(5) comp-3.
    05 count-a pic 9(4) comp.
    05 marker-a pic x.
01 raw-record pic x(6).
working-storage section.
01 file-state pic xx.
procedure division.
    open output records-file
    move -12345 to amount-a
    move 258 to count-a
    move "Q" to marker-a
    write raw-record
    move 0 to amount-a count-a
    move "Z" to marker-a
    write structured-record
    close records-file
    open input records-file
    read records-file
    display amount-a "|" count-a "|" marker-a
    read records-file
    display amount-a "|" count-a "|" marker-a
    read records-file at end display "EOF" end-read
    read records-file
    display file-state
    close records-file
    stop run.
