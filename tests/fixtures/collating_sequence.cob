identification division.
program-id. collating-sequence.
*> PROGRAM COLLATING SEQUENCE with a literal alphabet (validate_alphabet):
*> listed characters first, ALSO sharing a weight, the others after in
*> native order; HIGH-VALUE and LOW-VALUE follow it; alphanumeric
*> comparisons and SORT keys use the weights.
environment division.
configuration section.
object-computer. this-computer program collating sequence is backwards.
special-names.
    alphabet backwards is "Z" thru "A" "9" thru "0" " " "x" also "y" also "z".
input-output section.
file-control.
    select work-file assign to "COLWORK".
data division.
file section.
sd work-file.
01 work-rec pic x(3).
working-storage section.
01 a pic x(3) value "ABC".
01 b pic x(3) value "XYZ".
01 d pic 9 value 5.
01 letter pic x value "A".
01 hv pic x value high-value.
01 lv pic x value low-value.
01 low-ord pic 999.
01 high-ord pic 999.
procedure division.
    if a > b display "ABC > XYZ" else display "ABC <= XYZ".
    if "x" = "z" display "x = z" else display "x <> z".
    if "x" < "y" display "x < y" else display "x >= y".
    if d < letter display "5 < A" else display "5 >= A".
    if a < zero display "ABC < ZERO" else display "ABC >= ZERO".
    if a < space display "ABC < SPACE" else display "ABC >= SPACE".
    compute low-ord = function ord(lv).
    compute high-ord = function ord(hv).
    display "low=" low-ord " high=" high-ord.
    if lv < "Z" display "low < Z" else display "low >= Z".
    sort work-file on ascending key work-rec
        input procedure feed output procedure drain.
    stop run.
feed.
    move "AAA" to work-rec. release work-rec.
    move "9ZZ" to work-rec. release work-rec.
    move "ZAA" to work-rec. release work-rec.
    move "aaa" to work-rec. release work-rec.
drain.
    return work-file at end go to drained end-return.
    display "sorted: " work-rec.
    go to drain.
drained.
    exit.
