       >>source format free
identification division.
program-id. report-source-capture.
environment division.
input-output section.
file-control.
    select print-file assign to 'capture.txt'
        organization line sequential.
data division.
file section.
fd print-file report is report-a.
working-storage section.
01 control-a pic 9 value 1.
01 position-a pic 9 value 2.
01 length-a pic 9 value 2.
01 text-a pic x(6) value 'ABCDEF'.
01 table-a.
   02 name-a occurs 2 pic x(4).
   02 amount-a occurs 2 pic s99v9 comp-3.
   02 edited-a occurs 2 pic -99.9.
   02 scaled-a occurs 2 pic 99pp.
report section.
rd report-a controls control-a
    page limit 20 first detail 1 last detail 18.
01 detail-a type detail.
   02 line plus 1.
      03 column 1 pic x value 'D'.
      03 column 3 pic 9 source control-a.
      03 column 5 pic x(4) source name-a(control-a).
      03 column 10 pic x(4) source name-a(1).
      03 column 15 pic x(3) source text-a(2:3).
      03 column 19 pic x(6) source text-a(position-a:length-a).
      03 column 26 pic x(6) source text-a(3:).
      03 column 33 pic +99.9 source amount-a(control-a).
      03 column 39 pic +99.9 source edited-a(control-a).
      03 column 45 pic 9(4) source scaled-a(control-a).
      03 column 50 pic 99 source line-counter.
01 footer-a type control footing control-a.
   02 line plus 1.
      03 column 1 pic x value 'F'.
      03 column 3 pic 9 source control-a.
      03 column 5 pic x(4) source name-a(control-a).
      03 column 10 pic x(4) source name-a(1).
      03 column 15 pic x(3) source text-a(2:3).
      03 column 19 pic x(6) source text-a(position-a:length-a).
      03 column 26 pic x(6) source text-a(3:).
      03 column 33 pic +99.9 source amount-a(control-a).
      03 column 39 pic +99.9 source edited-a(control-a).
      03 column 45 pic 9(4) source scaled-a(control-a).
procedure division.
    move 'AAAA' to name-a(1)
    move 'BBBB' to name-a(2)
    move -12.3 to amount-a(1) edited-a(1)
    move 45.6 to amount-a(2) edited-a(2)
    move 1200 to scaled-a(1)
    move 3400 to scaled-a(2)
    open output print-file
    initiate report-a
    generate detail-a
    move 2 to control-a
    move 3 to position-a length-a
    move 'UVWXYZ' to text-a
    generate detail-a
    move 1 to control-a position-a
    move 4 to length-a
    move 'abcdef' to text-a
    move 98.7 to amount-a(1) edited-a(1)
    terminate report-a
    close print-file
    goback.
