identification division.
program-id. nested-main.
data division.
working-storage section.
01 shared-ext is external.
   02 ext-count pic 99.
   02 ext-text pic x(4).
01 shared-glob global.
   02 glob-count pic 99 value 10.
   02 glob-text pic x(4) value "main".
01 local-count pic 99 value 1.
procedure division.
    move 0 to ext-count. move "init" to ext-text.
    call "inner-a".
    display "after a " glob-count " " glob-text " " local-count.
    call "inner-b".
    display "after b " glob-count " " glob-text.
    call "outer-sibling".
    display "after sibling " ext-count " " ext-text.
    stop run.
identification division.
program-id. inner-a.
data division.
working-storage section.
01 local-count pic 99 value 50.
procedure division.
    add 1 to glob-count local-count.
    move "a-in" to glob-text.
    display "in a " glob-count " " local-count.
    goback.
end program inner-a.
identification division.
program-id. inner-b is common.
procedure division.
    add 5 to glob-count.
    move "b-in" to glob-text.
    display "in b " glob-count.
    call "inner-c".
    goback.
identification division.
program-id. inner-c.
procedure division.
    add 100 to glob-count.
    display "in c " glob-count.
    goback.
end program inner-c.
end program inner-b.
end program nested-main.
identification division.
program-id. outer-sibling.
data division.
working-storage section.
01 shared-ext external.
   02 ext-count pic 99.
   02 ext-text pic x(4).
procedure division.
    add 7 to ext-count.
    move "sibl" to ext-text.
    goback.
end program outer-sibling.
