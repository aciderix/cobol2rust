*> lineseq_write evaluates IS_BAD_CHAR (*p++) several times: a control byte
*> is judged with the bytes that follow it (status 71).
identification division.
program-id. t.
environment division.
input-output section.
file-control.
    select out-file assign to "output.txt" organization line sequential
        file status is out-status.
data division.
file section.
fd out-file.
01 out-record pic x(10).
working-storage section.
01 out-status pic xx.
01 codes.
   02 code-byte pic x occurs 6.
01 k pic 9.
procedure division.
    move x"09080c1b0f01" to codes
    open output out-file
    perform varying k from 1 by 1 until k > 6
        move "a b" to out-record
        move code-byte(k) to out-record(2:1)
        write out-record
        display k " " out-status
    end-perform
    move x"0108" to out-record
    write out-record
    display "control then BS " out-status
    close out-file
    stop run.
