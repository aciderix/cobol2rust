identification division.
program-id. picture-l.
*> PICTURE L ... DEPENDING ON : groupe à FILLER OCCURS 1 TO n DEPENDING,
*> de taille fixe pour les groupes englobants.
data division.
working-storage section.
01 w-data.
   05 head     pic x value "<".
   05 x-dat    picture lx(6) depending on lgx.
   05 x-alpha  picture la(4) depending lgx.
   05 tail     pic x value ">".
01 w-redef.
   05 base     pic x(8).
   05 y-dat    redefines base picture lx(8) depending on lgy.
01 w-tab.
   05 cell     occurs 3 picture lx(3) depending on lgz.
01 g1.
   05 k        picture lx(5) depending on lgx.
   05 m        pic x(2) value "m1".
01 g2.
   05 k        pic x(5) value "kkkkk".
   05 m        picture lx(2) depending on lgx.
01 lgx         pic 9 value 6.
01 lgy         pic 9v9 value 3.7.
01 lgz         usage comp-1 value 2.
01 num         pic s99 value -12.
01 len         pic 99.
01 cnt         pic 99 value 0.
procedure division.
    move all "*" to x-dat
    display "[" w-data "] [" x-dat "] " function length (x-dat)
    move 3 to lgx
    move "abcdef" to x-dat
    move "QRST" to x-alpha
    display "[" w-data "] [" x-dat "] [" x-alpha "]"
    move length of x-dat to len
    display "length of " len " function " function length (x-dat)
            " group " function length (w-data)
    move num to x-dat
    display "[" x-dat "] [" w-data "]"
    if x-dat = "-12" display "eq" else display "ne" end-if
    if x-dat = "-1" display "eq2" else display "ne2" end-if
    move 0 to lgx
    display "[" x-dat "] " function length (x-dat) " [" w-data "]"
    move 2 to lgx
    initialize x-dat
    move 6 to lgx
    display "[" w-data "]"
    initialize w-data
    display "[" w-data "]"
    move "0123456789" to base
    display "[" y-dat "] " function length (y-dat)
    move "zz" to y-dat
    display "[" base "]"
    move all "#" to w-tab
    move "AB" to cell (2)
    move 3 to lgz
    display "[" w-tab "] [" cell (2) "] [" cell (3) "]"
    move 3 to lgx
    move "LLLLL" to k of g1
    move corresponding g1 to g2
    display "[" g1 "] [" g2 "]"
    inspect x-dat tallying cnt for all "1"
    string "s" "t" delimited by size into x-dat
    display cnt " [" x-dat "] [" x-dat (2:) "]"
    stop run.
