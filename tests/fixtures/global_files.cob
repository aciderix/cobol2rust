identification division.
program-id. glob-main.
environment division.
input-output section.
file-control.
    select optional g-file assign to "GLOBAL.TXT"
        organization line sequential.
    select log-file assign to "LOG.TXT"
        organization line sequential.
data division.
file section.
fd g-file global.
01 g-rec pic x(8).
01 g-alt.
    02 g-head pic x(3).
    02 g-tail pic x(5).
fd log-file.
01 log-rec pic x(20).
working-storage section.
01 hits pic 9 value 0 global.
01 local-count pic 9 value 0.
procedure division.
declaratives.
input-errors section.
    use global after error procedure on input.
input-1.
    add 1 to hits.
    add 1 to local-count.
    move "HANDLER" to log-rec.
    write log-rec.
    display "input handler " hits " " local-count.
    if local-count > 3
        go to input-end
    end-if.
    display "input handler continues".
input-end.
    exit.
output-errors section.
    use after error procedure on output.
output-1.
    display "main output handler".
end declaratives.
main-line section.
start-here.
    open output log-file.
    call "glob-child".
    display "back " hits " " local-count " [" g-rec "] [" g-head "]".
    call "glob-child-2".
    display "done " hits " " local-count.
    open output g-file.
    read g-file.
    close g-file.
    move "MAIN-END" to log-rec.
    write log-rec.
    close log-file.
    stop run.

identification division.
program-id. glob-child.
procedure division.
    open input g-file.
    read g-file.
    display "child after read " hits.
    close g-file.
    open output g-file.
    move "CHILD" to g-rec.
    write g-rec.
    move "SECOND" to g-rec.
    write g-rec.
    close g-file.
    exit program.
end program glob-child.

identification division.
program-id. glob-child-2.
data division.
working-storage section.
01 child-2-count pic 9 value 0.
procedure division.
declaratives.
own-input section.
    use after error procedure on input.
own-1.
    add 1 to child-2-count.
    display "child-2 own handler " child-2-count.
child-2-output section.
    use global after error procedure on output.
out-1.
    add 1 to child-2-count.
    display "child-2 global output handler " child-2-count " " hits.
end declaratives.
main-2 section.
m2.
    open input g-file.
    read g-file.
    display "child-2 read [" g-rec "]".
    read g-file.
    read g-file.
    display "child-2 at end " child-2-count.
    close g-file.
    call "glob-grandchild".
    display "child-2 back " child-2-count " " hits.
    exit program.

identification division.
program-id. glob-grandchild.
procedure division.
    open input g-file.
    read g-file.
    read g-file.
    read g-file.
    display "grandchild input " hits.
    close g-file.
    open extend g-file.
    move "GRAND" to g-rec.
    write g-rec.
    close g-file.
    open output g-file.
    read g-file.
    display "grandchild output " hits.
    close g-file.
    exit program.
end program glob-grandchild.
end program glob-child-2.
end program glob-main.
