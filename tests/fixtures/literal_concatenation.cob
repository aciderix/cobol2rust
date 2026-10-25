*> Alphanumeric literals joined by & form one literal at compile time.
identification division.
program-id. concatenation.
data division.
working-storage section.
01 joined pic x(12) value "ab" & "cd" & x"41".
procedure division.
    display "[" joined "]"
    display "one" & " " & "two"
    if joined(1:4) = "a" & "bcd" display "equal" end-if
    stop run.
