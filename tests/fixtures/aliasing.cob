identification division.
program-id. aliasing-demo.
data division.
working-storage section.
01 raw-a pic x(8) value "ABCDEFGH".
01 parts redefines raw-a.
    05 left-a pic x(4).
    05 right-a pic x(4).
01 saved-a pic x(8).
01 table-a.
    05 n occurs 3 times pic 9 value 0.
01 i pic 9 value 1.
01 saved-n pic 9.
procedure division.
    move raw-a to right-a saved-a
    display raw-a "/" saved-a
    move 2 to n(1)
    move 3 to n(2)
    move 4 to n(3)
    move n(i) to i saved-n
    display "I=" i " SAVED=" saved-n " TABLE=" table-a
    move 3 to i n(i)
    display "I=" i " TABLE=" table-a
    stop run.
