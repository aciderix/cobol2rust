identification division.
program-id. renames-items.
data division.
working-storage section.
01 rec.
   05 a pic x(3) value "ABC".
   05 g.
      10 n pic 9(3) value 123.
      10 b pic x(2) value "XY".
   05 c pic x value "Z".
   66 a-thru-b renames a thru b.
   66 just-n renames n.
   66 the-g renames g of rec.
   66 g-thru-c renames g through c.
procedure division.
    display a-thru-b "|" just-n "|" the-g "|" g-thru-c
    add 1 to just-n
    move "QQQQQQ" to the-g
    display rec
    move 7 to a-thru-b
    display rec
    move 5 to just-n
    display rec
    stop run.
