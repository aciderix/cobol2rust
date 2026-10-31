identification division.
program-id. report-column-plus.
environment division.
input-output section.
file-control.
    select report-file assign "report-column-plus.txt" organization line sequential.
data division.
file section.
fd report-file report is plus-report.
working-storage section.
01 counter pic 99 value 7.
report section.
rd plus-report page limit 10.
01 plus-detail type detail.
   05 line plus 1.
      10 col plus 4 pic x(3) value "AAA".
      10 col plus 2 pic x(2) value "BB".
      10 pic 99 source counter.
      10 col plus 0 pic x value "C".
      10 col 20 pic x value "D".
      10 col + 1 pic x value "E".
   05 line plus 1.
      10 group-item.
         15 col 3 pic x value "F".
         15 col plus 3 pic x value "G".
      10 col plus 1 pic x value "H".
procedure division.
    open output report-file
    initiate plus-report
    generate plus-detail
    initiate plus-report
    terminate plus-report
    close report-file
    stop run.
