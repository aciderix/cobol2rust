*> LENGTH OF (cb_build_length): a literal for a fixed item or a literal,
*> FUNCTION LENGTH for a reference modification, the current size of a group
*> with OCCURS DEPENDING (cb_build_length_1).
identification division.
program-id. length-of.
data division.
working-storage section.
01 name-text pic x(12) value "ABC".
01 amount pic s9(5)v99 comp-3.
01 table-a.
   02 entry-a pic x(3) occurs 4.
01 count-a pic 9 value 2.
01 variable-a.
   02 header-a pic x(2).
   02 item-a pic x(5) occurs 1 to 6 depending on count-a.
01 result pic 9(4).
01 start-at pic 9 value 3.
procedure division.
    display length of name-text
    display length name-text
    display length of amount
    display length of table-a " " length of entry-a (2)
    move length of variable-a to result
    display "odo " result
    move 5 to count-a
    compute result = length of variable-a + 1
    display "odo+1 " result
    move length of name-text (start-at:) to result
    display length of "quoted" " " result
    if length of name-text > 10 display "longer than 10" end-if
    stop run.
