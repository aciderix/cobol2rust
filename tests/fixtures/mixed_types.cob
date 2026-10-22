identification division.
program-id. mixed-types.
environment division.
input-output section.
file-control.
    select report-file assign to "mixed-report.txt"
        organization line sequential.
data division.
file section.
fd report-file.
01 report-record pic x(20).
working-storage section.
01 number-a pic 9(4) value 12.
01 text-a pic x(4) value "0012".
01 zero-text pic xxx value "000".
01 source-text pic x(8) value "-12.30".
01 parsed-text pic x(4) value "1230".
01 parsed-a pic s99v99.
01 edited-a pic -99.99.
01 result-text pic x(5).
procedure division.
    move source-text to parsed-a edited-a
    if number-a = text-a and zeroes = zero-text and parsed-a = parsed-text
        move "MATCH" to result-text
    else
        move "ERROR" to result-text
    end-if
    display "MIXED:[" result-text "][" parsed-a "][" edited-a "]"
    open output report-file
    write report-record from result-text
    write report-record from edited-a
    close report-file
    stop run.
