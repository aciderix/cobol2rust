identification division.
program-id. inspect-markers.
data division.
working-storage section.
01 x pic x(8) value "QAB.ZZ..".
01 n pic 99 value 0.
01 m pic 99 value 0.
01 w pic x(3000).
01 k pic 9(4) value 0.
procedure division.
    *> LEADING marks one position less than it counts.
    inspect x tallying n for all "Z" leading "A" after "Q"
    display n
    *> Its empty mark leaves libcob's marker minimum on an unmarked
    *> position: the next INSPECT does not clear the stale marks.
    inspect x tallying m for all "Q" characters
    display m
    move 0 to m
    inspect x tallying m for all "Q" characters
    display m
    *> A larger target reallocates the marker buffer.
    move all "ab" to w
    inspect w tallying k for all "a" characters
    display k
    move 0 to m
    inspect x tallying m for all "Q" characters
    display m
    stop run.
