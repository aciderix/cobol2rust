identification division.
program-id. ENTSUB.
data division.
working-storage section.
01 calls pic 9 value 0.
linkage section.
01 text-arg pic x(6).
01 count-arg pic 9(4).
procedure division using text-arg count-arg.
    add 1 to calls
    display "main entry " calls " [" text-arg "]"
    move "MAIN" to text-arg.
second-part.
    entry "ENTALT" using count-arg.
    add 1 to calls
    add 100 to count-arg
    display "through ENTALT " calls " [" count-arg "]"
    goback.
