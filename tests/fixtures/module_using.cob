*> PROCEDURE DIVISION USING: a module (cobc -x refuses it), run as cobcrun
*> runs it, without arguments; EXIT PROGRAM returns to cobcrun, which ends
*> the run unit with RETURN-CODE.
identification division.
program-id. modusing.
data division.
working-storage section.
01 counter pic 9 value 4.
linkage section.
01 parameter-a pic x(8).
procedure division using parameter-a.
    display "module without arguments " counter
    move 3 to return-code
    exit program.
