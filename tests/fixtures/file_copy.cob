identification division.
program-id. file-copy-demo.
environment division.
input-output section.
file-control.
    select source-file assign to "source.txt"
        organization line sequential access mode sequential file status input-status.
    select target-file assign to "target.txt"
        organization line sequential file status output-status.
data division.
file section.
fd source-file.
01 input-record pic x(6).
fd target-file.
01 output-record pic x(10).
working-storage section.
01 input-status pic xx.
01 output-status pic xx.
01 buffer-text pic x(8).
01 finished pic 9 value 0.
01 total pic 999 value 0.
procedure division.
    open input source-file output target-file
    perform until finished = 1
        read source-file into buffer-text
            at end move 1 to finished
            not at end
                write output-record from buffer-text
                add 1 to total
        end-read
    end-perform
    close source-file target-file
    display "Copies=" total "/" input-status "/" output-status
    stop run.
