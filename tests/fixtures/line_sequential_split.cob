*> lineseq_read with COB_LS_SPLIT and COB_LS_VALIDATE (GnuCOBOL 3.2 defaults):
*> a long line continues in the next record (06), control characters give
*> 09, a CR alone is data; lineseq_write refuses control characters (71).
identification division.
program-id. ls-split.
environment division.
input-output section.
file-control.
    select in-file assign to "input.txt" organization line sequential
        file status is in-status.
    select out-file assign to "output.txt" organization line sequential
        file status is out-status.
data division.
file section.
fd in-file.
01 in-record pic x(8).
fd out-file.
01 out-record pic x(10).
working-storage section.
01 in-status pic xx.
01 out-status pic xx.
01 eof pic x value "n".
procedure division.
    open input in-file output out-file
    perform until eof = "y"
        move all "#" to in-record
        read in-file
            at end move "y" to eof
            not at end
                display in-status " [" in-record "]"
                move in-record to out-record
                write out-record
                display "write " out-status
        end-read
    end-perform
    move "tab ok" to out-record
    move x"09" to out-record(4:1)
    write out-record
    display "write tab " out-status
    move "bad" to out-record
    move x"01" to out-record(4:1)
    write out-record after advancing 2 lines
    display "write control " out-status
    close in-file out-file
    stop run.
