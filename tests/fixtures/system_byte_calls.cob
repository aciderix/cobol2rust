       >>source format free
identification division.
program-id. system-byte-calls.
environment division.
input-output section.
file-control.
    select byte-file assign 'system-bytes.bin'
        organization sequential.
data division.
file section.
fd byte-file record contains 256 characters.
01 byte-record pic x(256).
working-storage section.
01 input-a pic x(256).
01 initial-b pic x(256).
01 input-b pic x(256).
01 index-a pic 9(4).
01 char-code pic 9(4).
01 call-name pic x(16).
procedure division.
    perform varying index-a from 1 by 1 until index-a > 256
        move function char(index-a) to input-a(index-a:1)
        compute char-code = function mod(index-a * 73 + 41, 256) + 1
        move function char(char-code) to initial-b(index-a:1)
    end-perform
    open output byte-file
    perform reset-target
    call 'CBL_AND' using input-a input-b by value 256 end-call
    perform emit-target
    perform reset-target
    call 'CBL_OR' using input-a input-b by value 256 end-call
    perform emit-target
    perform reset-target
    call 'CBL_NOR' using input-a input-b by value 256 end-call
    perform emit-target
    perform reset-target
    call 'CBL_XOR' using input-a input-b by value 256 end-call
    perform emit-target
    perform reset-target
    call 'CBL_IMP' using input-a input-b by value 256 end-call
    perform emit-target
    perform reset-target
    call 'CBL_NIMP' using input-a input-b by value 256 end-call
    perform emit-target
    perform reset-target
    call 'CBL_EQ' using input-a input-b by value 256 end-call
    perform emit-target
    perform reset-target
    call 'CBL_NOT' using input-b by value 256 end-call
    perform emit-target
    move input-a to input-b
    move 91 to return-code
    call 'C$TOUPPER' using input-b by value 256 end-call
    perform emit-target
    move input-a to input-b
    move 91 to return-code
    call 'C$TOLOWER' using input-b by value 256 end-call
    perform emit-target
    move input-a to input-b
    move 91 to return-code
    move 'CBL_TOUPPER' to call-name
    call call-name using input-b by value 256
        on exception display 'unresolved upper' stop run returning 1
        not on exception continue
    end-call
    perform emit-target
    move input-a to input-b
    move 91 to return-code
    move 'CBL_TOLOWER' to call-name
    call call-name using input-b by value 256
        on exception display 'unresolved lower' stop run returning 1
        not on exception continue
    end-call
    perform emit-target
    close byte-file
    display 'byte calls OK'
    stop run.
reset-target.
    move initial-b to input-b
    move 91 to return-code.
emit-target.
    if return-code not = 0
        display 'bad system return code'
        stop run returning 1
    end-if
    move input-b to byte-record
    write byte-record.
