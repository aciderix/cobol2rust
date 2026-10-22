identification division.
program-id. edited-report.
environment division.
input-output section.
file-control.
    select report-file assign to "edited-report.txt" organization sequential.
data division.
file section.
fd report-file
    label records omitted
    block contains 0 records
    record contains 10 characters
    recording mode f.
01 report-record.
    05 prefix-a pic x(3).
    05 printed-amount pic -9(3).99.
01 report-raw pic x(10).
working-storage section.
01 suppressed-amount pic ZZZ9.99.
procedure division.
    open output report-file
    move "POS" to prefix-a
    compute printed-amount rounded = 1.245
    write report-raw before advancing 1 line
    move "NEG" to prefix-a
    compute printed-amount rounded = -1.245
    write report-record before advancing 1 line
    move "OVF" to prefix-a
    compute printed-amount rounded = 1234.995
    write report-raw before advancing 1 line
    display report-raw
    move -12.3 to suppressed-amount
    display "Z=[" suppressed-amount "]"
    close report-file
    stop run.
