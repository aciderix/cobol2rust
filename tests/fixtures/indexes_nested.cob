identification division.
program-id. indexes-nested.
data division.
working-storage section.
01 a.
 05 row-a occurs 2 indexed by outer-idx.
  10 tag-a pic x value 'A'.
  10 column-a occurs 3 indexed by inner-idx second-idx pic xx value 'BC'.
01 b.
 05 other-a occurs 3 indexed by other-idx pic x(5) value 'HELLO'.
01 result-a pic s9(9) comp.
procedure division.
display outer-idx '/' inner-idx
set outer-idx to 2
set inner-idx second-idx to 1
set inner-idx second-idx up by inner-idx
display inner-idx '/' second-idx
set other-idx to inner-idx
move 'ZZ' to column-a(outer-idx, inner-idx)
display column-a(2, 2) '/' other-a(other-idx)
set second-idx down by 3
move second-idx to result-a
display result-a
perform varying outer-idx from 1 by 1 until outer-idx > 2
 perform varying inner-idx from 1 by 1 until inner-idx > 3
  display column-a(outer-idx, inner-idx) with no advancing
 end-perform
end-perform
display 'END'
initialize other-idx
display other-idx
compute other-idx = 1000000000 on size error display 'BAD' end-compute
display other-idx
set other-idx to -2147483648
display other-idx
set other-idx to 2147483647
display other-idx
stop run.
