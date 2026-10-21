IDENTIFICATION DIVISION.
PROGRAM-ID. ordinal-indexes.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 g.
 05 cell-a occurs 4 indexed by idx idx2 pic xx value 'AB'.
01 result-a pic s9(9) comp.

PROCEDURE DIVISION.
set idx to 2
display idx
move idx to result-a display result-a
set idx2 to idx
set idx idx2 up by 1
display idx '/' idx2 '/' cell-a(idx)
set idx down by 4 display idx
perform varying idx from 1 by 1 until idx > 4
 display idx ':' cell-a(idx)
end-perform display idx
STOP RUN.
