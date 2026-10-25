*> Report Writer control breaks as reportio.c: CONTROLS (cobc's list runs
*> from the minor control), CONTROL HEADING/FOOTING, a footing printing the
*> previous control value, SUM counters rolled forward into the higher
*> levels, CONTROL FOOTING FINAL, NEXT GROUP PLUS/absolute/NEXT PAGE, page
*> overflow with PAGE HEADING and PAGE FOOTING, GROUP INDICATE.
identification division.
program-id. report-controls.
environment division.
input-output section.
file-control.
    select sales-file assign to "sales.txt" organization line sequential.
    select print-file assign to "report.txt".
data division.
file section.
fd sales-file.
01 sales-record.
   88 end-of-sales value high-values.
   02 region pic 99.
   02 agent pic xxx.
   02 amount pic 9(4).
fd print-file report is sales-report.
working-storage section.
report section.
rd sales-report
   controls are final region agent
   page limit is 24 lines
   heading 1 first detail 4 last detail 20 footing 22.
01 type report heading next group plus 1.
   02 line 1.
      03 column 10 pic x(12) value "SALES REPORT".
01 type page heading.
   02 line plus 1.
      03 column 1 pic x(6) value "REGION".
      03 column 9 pic x(5) value "AGENT".
      03 column 20 pic x(6) value "AMOUNT".
01 type control heading region.
   02 line plus 1.
      03 column 1 pic x(7) value "REGION ".
      03 column 8 pic 99 source region.
01 detail-line type detail.
   02 line plus 1.
      03 column 2 pic 99 source region group indicate.
      03 column 9 pic xxx source agent group.
      03 column 19 pic z,zz9 source amount.
01 agent-footing type control footing agent next group plus 1.
   02 line plus 1.
      03 column 5 pic x(10) value "AGENT SUM".
      03 column 15 pic xxx source agent.
      03 agent-total column 19 pic zz,zz9 sum amount.
01 region-footing type control footing region next group next page.
   02 line plus 1.
      03 column 3 pic x(10) value "REGION SUM".
      03 column 14 pic 99 source region.
      03 region-total column 18 pic zzz,zz9 sum agent-total.
      03 column 27 pic zzz9 sum amount.
01 type control footing final.
   02 line plus 2.
      03 column 1 pic x(11) value "GRAND TOTAL".
      03 column 17 pic z,zzz,zz9 sum region-total.
01 type page footing.
   02 line 23.
      03 column 1 pic x(5) value "PAGE ".
      03 column 6 pic z9 source page-counter.
procedure division.
    open input sales-file output print-file
    read sales-file at end set end-of-sales to true end-read
    initiate sales-report
    perform until end-of-sales
        generate detail-line
        read sales-file at end set end-of-sales to true end-read
    end-perform
    terminate sales-report
    close sales-file print-file
    stop run.
