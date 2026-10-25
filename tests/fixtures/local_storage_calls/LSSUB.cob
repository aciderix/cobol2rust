identification division.
program-id. LSSUB.
data division.
working-storage section.
01 persisting pic 9 value 0.
local-storage section.
01 fresh pic 9 value 5.
01 scratch.
   02 scratch-text pic x(3).
   02 scratch-number pic 99.
procedure division.
    add 1 to persisting fresh
    display "persisting " persisting " fresh " fresh " [" scratch-text "] [" scratch-number "]"
    move "XYZ" to scratch-text
    move 42 to scratch-number
    goback.
