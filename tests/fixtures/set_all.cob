*> MOVE ALL literal over texts, groups and substrings; SET integers TO an index.
identification division. program-id. set-all.
data division. working-storage section.
01 t. 02 e pic x(3) occurs 3 indexed by ix.
01 g. 02 a pic x(5). 02 n pic 9(3).
01 x pic x(7).
01 c1 pic 99. 01 c2 pic 9(4) comp.
procedure division.
    move all "AB" to g display "[" g "]"
    move all "XYZ" to x x(2:3) display "[" x "]"
    move all "Q" to t display "[" t "]"
    set ix to 3 set c1 c2 to ix display c1 " " c2
    set ix up by 1 set c1 to ix display c1
    stop run.
