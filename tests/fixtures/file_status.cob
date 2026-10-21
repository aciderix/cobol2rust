identification division.
program-id. file-status-demo.
environment division.
input-output section.
file-control.
    select f assign to "records.txt" organization line sequential file status fs.
    select missing-file assign to "absent.txt" organization line sequential file status fs.
    select optional opt assign to "optional.txt" organization line sequential file status fs.
data division.
file section.
fd f.
01 rec pic x(8).
fd missing-file.
01 absent-record pic x(8).
fd opt.
01 optional-record pic x(8).
working-storage section.
01 fs pic xx.
01 dest pic x(10) value "??????????".
procedure division.
    read f
    display "READ-CLOSED=" fs
    write rec
    display "WRITE-CLOSED=" fs
    close f
    display "CLOSE-CLOSED=" fs
    open input missing-file
    display "ABSENT=" fs
    open extend missing-file
    display "EXTEND-ABSENT=" fs
    close missing-file
    display "CLOSE-ABSENT=" fs
    open input opt
    display "OPTIONAL=" fs
    perform 3 times
        read opt
            at end display "OPTIONAL-END"
            not at end display "UNREACHABLE"
        end-read
        display "OPTIONAL-READ=" fs
    end-perform
    close opt
    display "OPTIONAL-CLOSE=" fs
    open extend opt
    display "OPTIONAL-EXTEND=" fs
    write optional-record from "CREATED"
    close opt
    open output f
    open output f
    display "ALREADY-OPEN=" fs
    read f
    display "READ-OUTPUT=" fs
    write rec from "ONE"
    close f
    open input f
    write rec
    display "WRITE-INPUT=" fs
    read f into dest not at end display "READ=" fs "[" dest "]" end-read
    read f into dest at end display "END=" fs "[" rec "][" dest "]" end-read
    read f at end display "UNREACHABLE" end-read
    display "READ-AFTER-END=" fs
    close f
    stop run.
