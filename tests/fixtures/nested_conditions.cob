identification division.
program-id. nested-conditions.
data division.
working-storage section.
01 a pic 9 value 1.
01 b pic 9 value 2.
01 c pic 9 value 1.
01 table-86.
   88 a86 value "ABC".
   88 b86 value "ABCAB".
   88 c86 value "ABCAB" thru "ABCAZ".
   02 dataname-86 pic xxx value "ABC".
   02 dname-86.
      03 filler pic x value "A".
      03 filler pic x value "B".
01 t. 05 e pic x occurs 20 indexed i1 i2.
01 n pic 9 value 0.
01 m pic 99 value 0.
procedure division.
    *> Without END-IF an ELSE pairs with the nearest open IF.
    if a = 1
        display "a1"
        if b = 1
            display "b1"
            if c = 1
                display "c1"
            else
                display "c2"
        else
            display "b2"
            if c = 1
                display "c3"
            else
                display "c4"
    else
        display "a2".
    *> Level 88 on a group compares its storage as text.
    if a86 display "a" else display "not a" end-if
    if b86 display "b" else display "not b" end-if
    if c86 display "c" else display "not c" end-if
    set a86 to true
    display table-86
    *> SET with index and integer receivers.
    set i1 to 4
    set i2 n m to i1
    display n " " m
    stop run.
