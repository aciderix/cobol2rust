       >>source format free
identification division.
program-id. any-main.
data division.
working-storage section.
01 arg pic x(7) value 'ABABABA'.
procedure division.
    call 'ANYCOND' using arg
    stop run.
end program any-main.

identification division.
program-id. ANYCOND.
data division.
linkage section.
01 arg pic x any length.
   88 all-filled value all 'AB' when set to false 'Y'.
   88 high-filled value high-values.
   88 low-filled value low-values.
   88 quote-filled value quotes.
   88 zero-filled value zeros.
   88 space-filled value spaces when set to false high-values.
procedure division using arg.
    if all-filled display 'all-ok' end-if
    set all-filled to true
    display 'ALL:[' arg ']'
    set high-filled to true
    if high-filled display 'high-ok' end-if
    set low-filled to true
    if low-filled display 'low-ok' end-if
    set quote-filled to true
    if quote-filled display 'quote-ok' end-if
    set zero-filled to true
    display 'ZERO:[' arg ']'
    set space-filled to true
    if space-filled display 'space-ok' end-if
    set all-filled to false
    display 'FALSE:[' arg ']'
    set space-filled to false
    if high-filled display 'false-high-ok' end-if
    move all 'X' to arg
    initialize arg
    display 'INIT:[' arg ']'
    initialize arg replacing alphanumeric by 'ABC'
    display 'REPLACE:[' arg ']'
    goback.
end program ANYCOND.
