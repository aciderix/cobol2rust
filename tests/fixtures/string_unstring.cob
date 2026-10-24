identification division.
program-id. string-unstring.
data division.
working-storage section.
01 dst pic x(12) value all "*".
01 ptr pic 99 value 3.
01 src pic x(16) value "AB,CD,,EF;GH   I".
01 a pic x(4).
01 b pic x(3).
01 c pic x(2) justified right.
01 n pic 9(3).
01 sn pic s9v9.
01 dl pic x(2).
01 dn pic 9.
01 cnt pic 99.
01 tl pic 9 value 8.
01 p2 pic 99.
procedure division.
    string "XY" "Z12" delimited by size "ab cd" delimited by space
           src delimited by "," into dst with pointer ptr
        on overflow display "ovf1" not on overflow display "ok1"
    end-string
    display dst " " ptr
    move all "-" to dst
    string src delimited by size into dst
        on overflow display "ovf2"
    end-string
    display dst
    move 13 to ptr
    string "Q" into dst pointer ptr on overflow display "ovf3" end-string
    display dst " " ptr
    unstring src delimited by "," or ";" into a delimiter in dl count in cnt
        b delimiter dl count cnt c n
        with pointer p2 tallying in tl
        on overflow display "uovf"
        not on overflow display "uok"
    end-unstring
    display a "|" b "|" c "|" n "|" dl "|" cnt "|" p2 "|" tl
    move 2 to p2
    move 0 to tl
    unstring src delimited by "," or ";" or "GH" into a delimiter in dl count in cnt
        b delimiter dl count cnt c delimiter in dn n
        with pointer p2 tallying in tl
        on overflow display "uovf"
        not on overflow display "uok"
    end-unstring
    display a "|" b "|" c "|" n "|" dl "|" dn "|" cnt "|" p2 "|" tl
    move 1 to p2
    unstring src delimited by all "," into a b c pointer p2
    display a "|" b "|" c "|" p2
    unstring src into a b
    display a "|" b
    move "12.5 7" to src
    unstring src delimited by space into sn dn delimiter in dn count in cnt
    display sn "|" dn "|" cnt
    move 0 to tl
    unstring src delimited by all space into a b c tallying tl
       not on overflow display "nov"
    end-unstring
    display a "|" b "|" c "|" tl
    stop run.
