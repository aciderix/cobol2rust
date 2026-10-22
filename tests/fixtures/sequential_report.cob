identification division.
program-id. sequential-report.
environment division.
input-output section.
file-control.
    select report-file assign to "report.txt" organization sequential.
data division.
file section.
fd report-file.
01 print-record pic x(8).
01 alternate-record pic x(8).
procedure division.
    open output report-file
    write print-record from "HEAD" after advancing page
    write alternate-record from "ROW1" before advancing 2 lines
    write print-record from "TAIL" after advancing 0 lines
    display "REPORT-OK"
    stop run.
