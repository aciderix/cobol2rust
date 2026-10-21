IDENTIFICATION DIVISION.
PROGRAM-ID. variable-text.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 n pic 9 value 2.
01 g.
  05 head-a pic x value 'H'.
  05 cell-a occurs 0 to 4 depending on n pic xx value 'AB'.
01 other-a pic x value 'Z'.

PROCEDURE DIVISION.
display '[' g ']/' other-a
move 4 to n
display '[' g ']'
move 'ZZ' to cell-a(4)
move 1 to n
initialize g
move 4 to n
display '[' g ']'
move 0 to n
display '[' g ']'
move 2 to n
move '123456789' to g
move 4 to n
display '[' g ']' 
STOP RUN.
