identification division.
program-id. any-length-main.
data division.
working-storage section.
01 short-a pic x(6) value 'ABCDEF'.
01 long-a pic x(9) value '123456789'.
01 group-a.
   05 part-a pic xx value 'HI'.
   05 part-b pic xxx value 'JKL'.
01 number-a pic s9(4)v99 value -123.45.
procedure division.
    call 'ANYREAD' using short-a
    call 'ANYREAD' using by content long-a
    call 'ANYREAD' using 'literal'
    call 'ANYREAD' using short-a(2:4)
    call 'ANYREAD' using group-a
    call 'ANYREAD' using number-a
    call 'ANYEDIT' using short-a
    display 'caller|' short-a '|'
    call 'ANYEDIT' using by content long-a
    display 'content|' long-a '|'
    call 'ANYRIGHT' using long-a
    display 'right|' long-a '|'
    goback.
end program any-length-main.

identification division.
program-id. ANYREAD.
data division.
linkage section.
01 arg any length.
procedure division using arg.
    display 'read|' length of arg '|' function length(arg) '|'
        function length(arg(2:)) '|' arg '|' arg(2:) '|'
    goback.
end program ANYREAD.

identification division.
program-id. ANYEDIT.
data division.
working-storage section.
01 number-a pic 9(4) value 1234.
01 count-a pic 99.
01 pointer-a binary-long.
01 part-a pic x(12).
linkage section.
01 arg pic x any length.
procedure division using arg.
    move 'ab' to arg
    display 'move|' arg '|'
    move 'XY' to arg(3:)
    display 'slice|' arg '|'
    move all 'Q' to arg
    if arg = all 'Q' display 'all-equal' end-if
    initialize arg
    display 'initialize|' arg '|'
    initialize arg replacing alphanumeric by 'ABC'
    display 'replace|' arg '|'
    move all 'AB' to arg
    move zero to count-a
    inspect arg tallying count-a for all 'AB'
    inspect arg replacing all 'AB' by 'cd'
    display 'inspect|' count-a '|' arg '|'
    move 2 to pointer-a
    string 'XYZ' delimited by size into arg with pointer pointer-a
        on overflow display 'overflow'
    end-string
    display 'string|' arg '|'
    unstring arg delimited by 'Z' into part-a end-unstring
    display 'unstring|' part-a '|'
    move number-a to arg
    display 'numeric|' arg '|'
    call 'ANYREAD' using arg
    goback.
end program ANYEDIT.

identification division.
program-id. ANYRIGHT.
data division.
linkage section.
01 arg pic x justified any length.
procedure division using arg.
    move 'END' to arg
    goback.
end program ANYRIGHT.
