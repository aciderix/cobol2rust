identification division.
program-id. special-names-case.
environment division.
configuration section.
source-computer. GNU-Linux.
object-computer. GNU-Linux program collating sequence is std2.
special-names.
    sysout is printer-out
    sysin is keyboard
    sysout is report-out
    switch-1 is sw-1 on status is sw1-on off status is sw1-off
    switch-2 is sw-2 on is sw2-on off is sw2-off
    switch-3 off status is sw3-off
    alphabet std2 is standard-2
    alphabet unused-alpha is "A" thru "E" "Z" also "Y"
    class hexa is "0" thru "9" "A" thru "F"
    class vowels is "AEIOU"
    symbolic characters star bang are 43 34.
data division.
working-storage section.
01 h pic x(4) value "1F0A".
01 v pic x(3) value "AEZ".
01 s pic x(3) value star.
01 inp pic x(5).
procedure division.
    display "[" s "]" upon printer-out
    display star bang upon report-out
    if sw1-on display "sw1 on" else display "sw1 off" end-if
    if sw2-on display "sw2 on" else display "sw2 off" end-if
    if sw3-off display "sw3 off" end-if
    set sw-1 to on
    if sw1-on display "sw1 now on" end-if
    set sw-1 sw-2 to off
    if sw1-off and sw2-off display "both off" end-if
    if h is hexa display "hexa" end-if
    if v is not vowels display "not vowels" end-if
    if v not hexa display "not hexa" end-if
    accept inp from keyboard
    display "read [" inp "]"
    display "to stderr" upon syserr
    display all "AB" "[" quote space "]"
    if "A" < "B" display "collating ok" end-if
    stop run.
