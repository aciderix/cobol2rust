identification division.
program-id. communication.
environment division.
configuration section.
source-computer. linux with debugging mode.
data division.
working-storage section.
01 work-area pic x(20) value "WORK".
01 hits pic 9 value 0.
communication section.
cd in-cd for initial input.
01 in-rec.
    02 in-queue pic x(12) value "INPUTQUEUE1".
    02 in-count pic 9(6).
    02 filler pic x(69) value spaces.
01 in-alt pic x(87).
cd out-cd for output.
01 out-rec.
    02 out-count pic 9(4) value 1.
    02 out-len pic 9(4).
    02 out-dest pic x(12) value "OUTPUTQUEUE1".
procedure division.
declaratives.
dbg section.
    use for debugging on in-cd out-cd.
dbg-1.
    add 1 to hits.
    display "debug " debug-line " [" debug-name "]".
end declaratives.
main section.
m.
    display "len " function length(debug-contents) " " function length(debug-item)
            " " function length(in-alt).
    display "[" in-queue "] [" out-dest "]".
    move "Q" to in-alt(1:1).
    display "[" in-queue(1:3) "]".
    enable input in-cd with key "K1".
    enable output out-cd.
    receive in-cd message into work-area
        with data display "data"
        no data display "no data"
    end-receive.
    display "after receive [" work-area "]".
    send out-cd from work-area with emi.
    send out-cd from work-area with egi after advancing 2 lines.
    send out-cd from work-area.
    accept in-cd message count.
    move 72 to out-len.
    display "out-len " out-len.
    disable output out-cd.
    disable input terminal in-cd with key work-area.
    purge out-cd.
the-end.
    display "hits " hits " " debug-line.
    stop run.
