identification division.
program-id. report-writer.
environment division.
input-output section.
file-control.
    select listing assign to "LISTING.TXT" file status is listing-status.
    select summary assign to "SUMMARY.TXT".
data division.
file section.
fd listing
    reports are sales-report.
fd summary
    report is short-report.
working-storage section.
01 listing-status pic xx.
01 item-name pic x(10).
01 amount pic s9(4)v99.
01 n pic 99.
01 counter-copy pic z9.
report section.
rd sales-report
    page limits are 16 lines
    heading 2
    first detail 5
    last detail 12
    footing 14.
01 type report heading.
    03 line 2 column 10 pic x(12) value "SALES REPORT".
01 page-head line number is 3 type is page heading.
    03 column 1 pic x(5) value "PAGE ".
    03 column 6 pic z9 source page-counter.
    03 column 12 pic x(5) value "LINE ".
    03 column 17 pic 99 source line-counter of sales-report.
01 sale-line type detail line plus 1.
    03 column 3 pic x(10) source item-name.
    03 column 15 pic -(4)9.99 source amount.
    03 column 26 pic 99 source line-counter.
01 two-lines type de.
    03 line plus 2.
        05 column 5 pic x(6) value "FIRST ".
        05 column 11 pic x(10) source item-name.
    03 line plus 1 column 7 pic x(6) value "SECOND".
01 fixed-line type detail line 11.
    03 column 2 pic x(9) value "AT LINE 1".
    03 column 11 pic x value "1".
01 type page footing line 15.
    03 column 4 pic x(7) value "FOOTING".
    03 column 12 pic 9 source page-counter.
01 type rf line plus 1.
    03 column 1 pic x(3) value "END".
rd short-report
    page 6.
01 short-line type detail line plus 1.
    03 column 1 pic x(10) source item-name.
procedure division.
    display "before " line-counter of short-report " " page-counter of sales-report.
    open output listing summary.
    initiate sales-report short-report.
    move line-counter of sales-report to counter-copy.
    display "initiated [" counter-copy "]".
    perform varying n from 1 by 1 until n > 9
        move "ITEM" to item-name
        move n to item-name(5:2)
        compute amount = n * 12.5 - 40
        generate sale-line
        if n = 3 or n = 7
            generate two-lines
        end-if
        move line-counter of sales-report to counter-copy
        display n " line " counter-copy " page " page-counter of sales-report
        generate short-line
    end-perform.
    generate fixed-line.
    generate sales-report.
    display "after group " line-counter of sales-report.
    terminate sales-report.
    terminate short-report.
    display "status " listing-status.
    close listing summary.
    open extend summary.
    initiate short-report.
    move "AGAIN" to item-name.
    generate short-line.
    terminate short-report.
    close summary.
    stop run.
