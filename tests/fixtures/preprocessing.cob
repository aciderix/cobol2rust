replace off.
identification division.
program-id. preprocessing-case.
environment division.
configuration section.
special-names.
    switch-1 is sw-1 on status is sw-1-on
    switch-2 is sw-2 off status is sw-2-off.
input-output section.
file-control.
    select unused assign to "UNUSED.TXT".
i-o-control.
data division.
file section.
fd unused.
01 unused-line pic x(4).
working-storage section.
replace ==counter-pic== by ==pic 99==
        ==move zero to counter display==
        by ==display==.
01 counter counter-pic value 3.
01 pair.
   02 half pic x(2) value "ab".
   02 half pic x(2) value "cd".
01 flag pic x value "N".
replace off.
procedure division.
    move zero to counter display
        "replaced " counter.
    display pair.
    perform test before until counter > 5
        add 1 to counter
    end-perform.
    perform with test after until counter > 2
        display "after " counter
    end-perform.
    copy LIBTEXT of "preplib".
    copy LIBTEXT.
    set sw-1 to on sw-2 to off.
    if sw-1-on and sw-2-off display "switches set" end-if.
    call "MISSING-PROGRAM"
        on exception
            add 1 to counter
            move "E" to flag
        not on exception
            move "N" to flag
    end-call.
    display flag " " counter.
    replace ==counter== by ==flag==.
    display "now " counter.
    stop run.
