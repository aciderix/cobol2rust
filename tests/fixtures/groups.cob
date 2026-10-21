identification division.
program-id. groups-demo.
data division.
working-storage section.
01 customer.
    05 name-a pic x(5) value "ALICE".
    05 filler pic x value "|".
    05 address-a.
        10 zip-code pic 9(5) value 75001.
        10 city-a pic x(5) value "PARIS".
01 backup-record.
    05 name-a pic x(5).
    05 filler pic x value "/".
    05 address-a.
        10 zip-code pic 9(5).
        10 city-a pic x(5).
procedure division.
    display "INITIAL=[" customer "]"
    move customer to backup-record
    move "BOB" to name-a of customer
    add 1 to zip-code in address-a of customer
    display "CURRENT=[" customer "]"
    display "BACKUP=[" backup-record "]"
    display name-a of backup-record "/" zip-code of backup-record
    initialize customer
    display "INIT=[" customer "]"
    initialize backup-record with filler
    display "FILLER=[" backup-record "]"
    stop run.
