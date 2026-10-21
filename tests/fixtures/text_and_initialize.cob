identification division.
program-id. text-init.
data division.
working-storage section.
01 a pic x(5) value "ABCDE".
01 b pic x(3) value spaces.
01 n pic 999 value 123.
procedure division.
    move a to b
    display "[" b "]"
    move "Z" to a b
    display "[" a "][" b "]"
    display "a*>b" " He said ""hi""" *> inline comment
    initialize a b n
    display "[" a "][" b "]" n
    stop run.
