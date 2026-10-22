identification division.
program-id. numeric-move-report.
environment division.
input-output section.
file-control.
    select report-file assign to "numeric-report.txt"
        organization line sequential file status report-status.
data division.
file section.
fd report-file.
01 report-record pic x(17).
working-storage section.
01 report-status pic xx.
01 pass-count pic 999 value 7.
01 error-count pic 999 value 0.
01 signed-count pic s999 value -12.
01 counts-line.
   02 pass-text pic xxx.
   02 filler pic x value "/".
   02 error-text pic xxx.
   02 filler pic x value "|".
   02 zero-text pic xxx.
01 literals-line.
   02 literal-zero pic xxx.
   02 filler pic x value "|".
   02 spelled-number pic x(6).
   02 filler pic x value "|".
   02 fractional-literal pic x(6).
01 plain-text pic x(5).
01 raw-group.
   02 raw-digits pic xxx.
   02 raw-padding pic xx.
procedure division.
    move pass-count to pass-text
    move error-count to error-text
    move zeros to zero-text
    move 0 to literal-zero
    move 0012 to spelled-number
    move -12.30 to fractional-literal
    move signed-count to plain-text raw-group
    display "COUNTS:[" counts-line "]"
    display "LITERALS:[" literals-line "]"
    display "TEXT:[" plain-text "]RAW:[" raw-group "]"
    open output report-file
    write report-record from counts-line
    write report-record from literals-line
    close report-file
    stop run.
