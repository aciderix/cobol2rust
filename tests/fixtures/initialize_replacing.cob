identification division.
program-id. initialize-replacing-case.
data division.
working-storage section.
01 rec.
   02 alpha pic a(3) value "abc".
   02 alnum pic x(4) value "wxyz".
   02 num pic 9(3) value 123.
   02 nedit pic zz9.99 value 1.5.
   02 aedit pic xbx value "p q".
   02 filler pic x(2) value "ff".
   02 tab occurs 2.
      03 cell pic 99 value 7.
      03 tag pic x value "t".
   02 alias redefines tab pic x(6).
01 other-rec.
   02 o-n pic 9(2) value 5.
   02 o-x pic x(2) value "oo".
procedure division.
    initialize rec replacing alphabetic data by "Q"
                             numeric data by 42.
    display "[" rec "]".
    initialize rec replacing alphanumeric by "-"
                             alphanumeric-edited by "uv"
                             numeric-edited data by 3.25.
    display "[" rec "]".
    initialize rec with filler replacing alphanumeric by "#".
    display "[" rec "]".
    initialize tab(2) replacing numeric by 9.
    display "[" rec "]".
    initialize other-rec.
    display "[" other-rec "]".
    stop run.
