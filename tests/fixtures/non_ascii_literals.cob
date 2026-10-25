*> Literals are bytes, as cobc reads its source: a UTF-8 "é" is two bytes,
*> X"..." gives any byte.
identification division.
program-id. non-ascii.
data division.
working-storage section.
01 word pic x(8) value "été".
01 other-word pic x(8).
01 counter pic 99 value 0.
01 bytes-field pic x(4) value x"00ff41c3".
procedure division.
    display "été [" word "] " function length("été")
    move "café" to other-word
    display "[" other-word "]"
    if word = "été" display "equal" end-if
    if word > "ete" display "greater" end-if
    inspect word tallying counter for all x"c3"
    display "tally " counter
    move x"c3a9" to other-word
    display "[" other-word "]"
    if bytes-field(2:1) = x"ff" display "ff" end-if
    if bytes-field(3:1) = "A" display "A" end-if
    stop run.
