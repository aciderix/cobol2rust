       >>source format free
identification division.
program-id. odo-capacity.
data division.
working-storage section.
01 count-a pic s99 value 2.
01 length-a pic 99.
01 group-a.
   05 marker-a pic x value 'P'.
   05 row-a occurs 0 to 4 depending on count-a indexed by index-a.
      10 letter-a pic x value 'A'.
      10 digit-a pic 9 value 1.
procedure division.
    move length of group-a to length-a
    display 'length|' length-a '|' group-a '|'
    move 'B4' to row-a(4)
    set index-a to 4
    display 'indexed|' row-a(index-a) '|'
    move 0 to count-a
    display 'zero|' row-a(4) '|'
    move 9 to count-a
    display 'high|' row-a(4) '|'
    move -1 to count-a
    display 'negative|' row-a(4) '|'
    move 2 to count-a
    display 'active|' group-a '|'
    goback.
