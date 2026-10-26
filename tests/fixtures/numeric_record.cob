*> An FD whose record is a numeric DISPLAY item: a view of the record area.
identification division.
program-id. numeric-record.
environment division.
input-output section.
file-control.
    select numbers-file assign to "numbers.txt" organization line sequential.
data division.
file section.
fd numbers-file.
01 number-rec pic 9(5).
working-storage section.
01 total pic 9(6) value 0.
procedure division.
    open output numbers-file
    move 42 to number-rec
    write number-rec
    move 1234 to number-rec
    write number-rec
    close numbers-file
    open input numbers-file
    read numbers-file
    add number-rec to total
    read numbers-file
    add number-rec to total
    close numbers-file
    display "total " total
    stop run.
