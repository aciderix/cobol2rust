identification division.
program-id. report-no-page.
environment division.
input-output section.
file-control.
    select out-file assign to "OUT.TXT".
data division.
file section.
fd out-file report is r.
working-storage section.
01 n pic 99 value 0.
report section.
rd r.
01 type report heading line plus 1.
    03 column 2 pic x(5) value "TITLE".
01 type page heading line plus 1.
    03 column 2 pic x(4) value "PAGE".
    03 column 8 pic 99 source page-counter.
01 type page footing line plus 1.
    03 column 2 pic x(4) value "FOOT".
01 type report footing line plus 2.
    03 column 1 pic x(3) value "END".
01 d type detail line plus 1.
    03 column 3 pic 99 source n.
    03 column 7 pic x(2) value "OK".
procedure division.
    open output out-file.
    initiate r.
    perform 3 times
        add 1 to n
        generate d
    end-perform.
    display "line " line-counter of r " page " page-counter of r.
    terminate r.
    close out-file.
    stop run.
