identification division.
program-id. init-main.
data division.
working-storage section.
01 round pic 9 value 0.
procedure division.
    perform 3 times
        add 1 to round
        call "init-sub" using round
        call "keep-sub"
    end-perform.
    cancel "init-sub".
    call "init-sub" using round.
    stop run.
end program init-main.

identification division.
program-id. init-sub is initial program.
environment division.
input-output section.
file-control.
    select optional log-file assign to "INITIAL.TXT"
        organization line sequential
        file status is log-fs.
data division.
file section.
fd log-file.
01 log-rec pic x(12).
working-storage section.
01 calls pic 9 value 0.
01 log-fs pic xx.
01 text-item pic x(4) value "INIT".
linkage section.
01 round pic 9.
procedure division using round.
    add 1 to calls.
    display "init-sub " calls " " text-item " round " round.
    move "USED" to text-item.
    open extend log-file.
    display "open " log-fs.
    move spaces to log-rec.
    string "ROUND " round delimited by size into log-rec.
    write log-rec.
    goback.
end program init-sub.

identification division.
program-id. keep-sub.
data division.
working-storage section.
01 calls pic 9 value 0.
procedure division.
    add 1 to calls.
    display "keep-sub " calls.
    goback.
end program keep-sub.
