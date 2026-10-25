identification division.
program-id. ext-main.
environment division.
input-output section.
file-control.
    select shared-file assign to "SHARED.TXT"
        organization line sequential
        file status is main-fs.
data division.
file section.
fd shared-file is external.
01 shared-rec pic x(10).
01 shared-alt.
    02 alt-a pic x(4).
    02 alt-b pic x(6).
working-storage section.
01 main-fs pic xx value "<>".
01 act pic x.
procedure division.
    open output shared-file.
    display "open " main-fs.
    move "MAIN-ONE" to shared-rec.
    write shared-rec.
    move "W" to act.
    call "ext-sub" using act.
    display "after sub write " main-fs " [" shared-rec "]".
    move "MAIN-TWO" to shared-rec.
    write shared-rec.
    move "C" to act.
    call "ext-sub" using act.
    display "main fs " main-fs.
    open input shared-file.
    move "R" to act.
    call "ext-sub" using act.
    display "main sees [" shared-rec "] [" alt-a "] " main-fs.
    read shared-file.
    display "main read [" shared-rec "] " main-fs.
    cancel "ext-sub".
    read shared-file.
    display "after cancel " main-fs.
    move "E" to act.
    call "ext-sub" using act.
    write shared-rec from "AFTER".
    display "main write " main-fs.
    close shared-file.
    open input shared-file.
    perform 5 times
        read shared-file
        display "final [" shared-rec "] " main-fs
    end-perform.
    close shared-file.
    stop run.
end program ext-main.

identification division.
program-id. ext-sub.
environment division.
input-output section.
file-control.
    select shared-file assign to "OTHER.TXT"
        organization line sequential
        file status is sub-fs.
data division.
file section.
fd shared-file external.
01 sub-rec pic x(10).
working-storage section.
01 sub-fs pic xx value "<>".
linkage section.
01 action pic x.
procedure division using action.
    evaluate action
        when "W"
            move "SUB-WRITE" to sub-rec
            write sub-rec
            display "sub write " sub-fs
        when "C"
            close shared-file
            display "sub close " sub-fs
        when "R"
            read shared-file
            display "sub read [" sub-rec "] " sub-fs
        when "E"
            open extend shared-file
            display "sub extend " sub-fs
    end-evaluate.
    goback.
end program ext-sub.
