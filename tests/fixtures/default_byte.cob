identification division.
program-id. default-byte.
*> defaultbyte: init (default) fills items without VALUE from their PICTURE
*> and sets INDEXED BY to 1; none (cobol85) leaves binary zeros.
environment division.
input-output section.
file-control.
    select f assign to "OUTF" organization sequential.
data division.
file section.
fd f.
01 rec.
   02 a pic x(3).
   02 b pic 9(3).
working-storage section.
01 w.
   02 wa pic x(3).
   02 wb pic 9(3).
01 wg. 02 wi pic 9(3) occurs 2 indexed by ix.
procedure division.
    open output f.
    write rec.
    move "xy" to a.
    write rec.
    close f.
    display "[" w "]" ix.
    stop run.
