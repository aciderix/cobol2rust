identification division.
program-id. external-main.
data division.
working-storage section.
01 shared-a pic x(6) external as "ext-name".
01 other_b pic x(4) external.
procedure division.
    move "abcdef" to shared-a
    move "1234" to other_b
    call "external-sub"
    display "main [" shared-a "] [" other_b "]"
    stop run.
end program external-main.
identification division.
program-id. external-sub.
data division.
working-storage section.
01 ext-name pic x(4) external.
01 other-b pic x(4) external.
procedure division.
    display "sub [" ext-name "] [" other-b "]"
    move "WXYZ" to ext-name
    move "9876" to other-b
    goback.
end program external-sub.
