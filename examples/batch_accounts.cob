identification division.
program-id. batch-accounts.
environment division.
input-output section.
file-control.
    select entries-file assign to "entries.txt"
        organization line sequential file status input-status.
    select balances-file assign to "balances.txt"
        organization line sequential file status output-status.
data division.
file section.
fd entries-file.
01 entry-record.
    05 operation-code pic x.
        88 credit-entry value "C".
        88 debit-entry value "D".
    05 account-number pic 99.
    05 entry-amount pic 9(5)v99.
fd balances-file.
01 balance-record.
    05 output-account pic 99.
    05 filler pic x.
    05 output-balance pic s9(7)v99.
working-storage section.
01 accounts-table.
    05 account-row occurs 5 times.
        10 account-balance pic s9(7)v99 comp-3 value 0.
01 input-status pic xx.
01 output-status pic xx.
01 eof-flag pic x value "N".
    88 finished value "Y".
01 accepted-count pic 999 value 0.
01 rejected-count pic 999 value 0.
01 i pic 99 value 0.
procedure division.
    initialize accounts-table
    open input entries-file output balances-file
    perform until finished
        read entries-file
            at end set finished to true
            not at end
                if account-number is numeric and entry-amount is numeric
                    and account-number >= 1 and account-number <= 5
                    evaluate true
                        when credit-entry
                            add entry-amount to account-balance(account-number)
                            add 1 to accepted-count
                        when debit-entry
                            subtract entry-amount from account-balance(account-number)
                            add 1 to accepted-count
                        when other
                            add 1 to rejected-count
                    end-evaluate
                else
                    add 1 to rejected-count
                end-if
        end-read
    end-perform
    perform varying i from 1 by 1 until i > 5
        move spaces to balance-record
        move i to output-account
        move account-balance(i) to output-balance
        write balance-record
        display "ACCOUNT=" i " BALANCE=" account-balance(i)
    end-perform
    close entries-file balances-file
    display "ACCEPTED=" accepted-count " REJECTED=" rejected-count
    stop run.
