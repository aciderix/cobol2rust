identification division.
program-id. exceptions.
environment division.
input-output section.
file-control.
    select missing assign "missing-exceptions.dat" status missing-status.
    select scratch assign "scratch-exceptions.dat" status scratch-status.
data division.
file section.
fd missing.
01 missing-record pic x(4).
fd scratch.
01 scratch-record pic x(4).
working-storage section.
01 missing-status pic xx.
01 scratch-status pic xx.
01 one pic 9 value 1.
01 zero-value pic 9 value 0.
01 small pic 9.
01 edited pic z9.
01 signed-result pic s99.
01 text-item pic x(4).
01 long-item pic x(6) value "abcdef".
01 from-item pic x(2) value "ab".
01 to-item pic x(3) value "xyz".
01 two pic 9 value 2.
01 text-pointer pic 99.
01 count-item pic 9 value 8.
01 pointer-item usage pointer.
01 status-text pic x(31).
procedure division.
    perform show
    open input missing
    perform show
    open output scratch
    display "after other file [" function exception-file "]"
    close scratch
    set last exception to off
    perform show
    divide one by zero-value giving small
    perform show
    compute small = 12
    perform show
    set last exception to off
    compute edited = 345
    perform show
    set last exception to off
    add 9 to small
    perform show
    set last exception to off
    compute small rounded mode prohibited = 1.5
    perform show
    set last exception to off
    divide one by zero-value giving small on size error display "handler"
    end-divide
    perform show
    compute small = 99 on size error display "size handler" end-compute
    perform show
    move function mod (-11 zero-value) to signed-result
    display "mod [" signed-result "]"
    perform show
    set last exception to off
    move function formatted-date ("YYYYMMDD", 0) to text-item
    perform show
    set last exception to off
    move 9 to text-pointer
    string "ab" delimited size into text-item with pointer text-pointer end-string
    perform show
    set last exception to off
    move 1 to text-pointer
    string "abcdef" delimited size into text-item with pointer text-pointer end-string
    perform show
    set last exception to off
    unstring long-item into text-item end-unstring
    perform show
    set last exception to off
    inspect text-item converting from-item to to-item(1:two)
    perform show
    set last exception to off
    inspect text-item tallying count-item for all "c"
    perform show
    set last exception to off
    free pointer-item
    perform show
    set pointer-item to address of text-item
    free pointer-item
    perform show
    set last exception to off
    allocate 2147483647 characters returning pointer-item
    perform show
    call "ABSENT-PROGRAM" on exception display "not found" end-display
    not on exception display "not on exception" end-display
    end-call
    perform show
    stop run.
show.
    move function exception-status to status-text
    display "[" status-text "][" function exception-location "]["
        function exception-statement "][" function exception-file "]".
