identification division.
program-id. redefines-demo.
data division.
working-storage section.
01 raw-record pic x(8) value "AB123456".
01 structured-record redefines raw-record.
    05 code-a pic xx.
    05 quantity pic 99.
    05 cost pic 9(4).
01 small-view redefines raw-record pic x(4).
01 copy-a pic x(8).
procedure division.
    display code-a "/" quantity "/" cost
    move "ZZ" to code-a
    compute quantity = quantity + 22
    display "RAW=" raw-record
    move raw-record to copy-a
    move "TT99" to small-view
    display "OVERLAY=" raw-record "/" quantity
    display "SNAPSHOT=" copy-a
    initialize structured-record
    display "INIT=[" raw-record "]"
    stop run.
