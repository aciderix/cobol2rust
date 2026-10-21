identification division.
program-id. file-demo.
environment division.
input-output section.
file-control.
    select transactions assign to "transactions.txt"
        organization is line sequential
        file status is io-status.
data division.
file section.
fd transactions.
01 transaction-record pic x(24).
working-storage section.
01 io-status pic xx.
01 finished pic 9 value 0.
01 records-read pic 999 value 0.
procedure division.
    open output transactions
    write transaction-record from "ALICE;00100.50"
    write transaction-record from "BOB;00025.00"
    close transactions
    open extend transactions
    write transaction-record from "CHARLIE;00010.25"
    close transactions
    open input transactions
    perform until finished = 1
        read transactions
            at end move 1 to finished
            not at end
                add 1 to records-read
                display transaction-record
        end-read
    end-perform
    display "Lignes=" records-read " Fin=" io-status
    close transactions
    stop run.
