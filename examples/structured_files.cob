identification division.
program-id. structured-file-demo.
environment division.
input-output section.
file-control.
    select invoices assign to "invoices.txt" organization line sequential file status io-status.
data division.
file section.
fd invoices.
01 invoice-record.
    05 customer-name pic x(10).
    05 filler pic x.
    05 quantity pic 999.
    05 unit-price pic 9(4)v99.
working-storage section.
01 io-status pic xx.
    88 io-ok value "00".
01 eof-flag pic x value "N".
    88 finished value "Y".
01 line-total pic 9(6)v99 value 0.
01 grand-total pic 9(7)v99 value 0.
procedure division.
    open output invoices
    move "ALICE     ;003001995" to invoice-record
    write invoice-record
    move "BOB       ;002001250" to invoice-record
    write invoice-record
    close invoices
    open input invoices
    perform until finished
        read invoices
            at end set finished to true
            not at end
                if quantity is numeric and unit-price is numeric
                    compute line-total = quantity * unit-price
                    add line-total to grand-total
                    display customer-name " TOTAL=" line-total
                end-if
        end-read
    end-perform
    close invoices
    if io-ok display "GRAND TOTAL=" grand-total end-if
    stop run.
