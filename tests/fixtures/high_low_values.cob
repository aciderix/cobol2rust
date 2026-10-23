identification division.
program-id. high-low-values.
data division.
working-storage section.
01 h pic xx value high-value.
01 l pic x(3) value low-values.
01 g.
   05 g1 pic x value "A".
   05 g2 pic x value high-values.
01 f pic x(2).
   88 f-high value high-values.
   88 f-low value low-value.
01 t pic x(4) value "ABCD".
01 gh value high-values.
   05 gh1 pic xx.
   05 gh2 pic x.
01 ab pic x(5) value "ABABA".
procedure division.
    display "[" h "][" l "][" g "]"
    move low-values to f
    if f-low display "low" end-if
    move high-values to f
    if f-high display "high" end-if
    if f = high-values display "eq high" end-if
    if t < high-values display "t < high" end-if
    if low-value < t display "low < t" end-if
    move high-value to t(2:2)
    display "[" t "]"
    if t > "AZ" display "t > AZ" end-if
    display "[" gh "]"
    if ab = all "AB" display "all ab" end-if
    if ab = all "A" display "all a" else display "not all a" end-if
    if all "A" < ab display "a < ab" end-if
    stop run.
