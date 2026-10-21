identification division.
program-id. odo-nested.
data division.
working-storage section.
01 n pic 9 value 1.
01 i pic 9.
01 g.
  05 head-a pic x value 'H'.
  05 sub-g.
    10 prefix-a pic x value 'A'.
    10 row-a occurs 1 to 3 depending on n indexed by idx.
      15 text-a pic x value 'X'.
      15 v occurs 2 indexed by sub-idx pic 9 value 1.
01 out-a pic x(12).
procedure division.
display '[' g ']/[' sub-g ']'
move 3 to n
set idx to 3
set sub-idx to 2
move 7 to v(idx, sub-idx)
display '[' g ']/[' row-a(idx) ']'
move 1 to n
move g to out-a
display '[' out-a ']'
move 'YZ33' to sub-g
move 3 to n
display '[' g ']'
move 1 to n
set idx to 1
initialize row-a(idx)
move 3 to n
display '[' g ']'
stop run.
