identification division.
program-id. initialize-value.
data division.
working-storage section.
01 record-a.
   05 a-text pic x(3) value "abc".
   05 a-number pic 9(3) value 12.
   05 filler pic x(2) value "fl".
   05 a-plain pic x(2).
   05 a-edited pic z9.99 value 1.5.
   05 a-packed pic s9(3) comp-3 value -7.
   05 a-redef redefines a-packed pic x(2).
   05 a-group value "GV".
      10 a-g1 pic x.
      10 a-g2 pic x.
01 table-a.
   05 row occurs 3.
      10 r-text pic x(2) value "vv".
      10 r-free pic x(2).
      10 r-number pic 99.
01 show-table redefines table-a pic x(18).
procedure division.
    move all "#" to record-a
    move all "#" to table-a
    initialize record-a all to value
    display "1 [" record-a "]"
    move all "#" to record-a
    initialize record-a with filler numeric to value
    display "2 [" record-a "]"
    move all "#" to record-a
    initialize record-a all value then to default
    display "3 [" record-a "]"
    move all "#" to record-a
    initialize record-a replacing alphanumeric by "R" then default
    display "4 [" record-a "]"
    move all "#" to record-a
    initialize record-a with filler replacing numeric by 5 default
    display "5 [" record-a "]"
    move "x1x2x3x4x5x6x7x8x9" to show-table
    initialize table-a all to value
    display "6 [" show-table "]"
    move "x1x2x3x4x5x6x7x8x9" to show-table
    initialize row (2) all to value then default
    display "7 [" show-table "]"
    move "x1x2x3x4x5x6x7x8x9" to show-table
    initialize table-a replacing numeric by 42 then to default
    display "8 [" show-table "]"
    move all "#" to record-a
    initialize a-edited a-text a-group all to value
    display "9 [" record-a "]"
    stop run.
