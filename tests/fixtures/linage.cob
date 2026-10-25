identification division.
program-id. linage-case.
environment division.
configuration section.
special-names.
    formfeed is to-top
    c01 is channel-1.
input-output section.
file-control.
    select paged assign to "PAGED.TXT" file status is paged-status.
    select sized assign to "SIZED.TXT" file status is sized-status.
    select plain assign to "PLAIN.TXT" organization is line sequential.
data division.
file section.
fd paged linage is 6 lines with footing at 5 lines at top 2 lines at bottom 1.
01 paged-line pic x(12).
fd sized linage page-size footing foot-size top 1.
01 sized-line pic x(12).
01 sized-other pic x(12).
fd plain.
01 plain-line pic x(12).
working-storage section.
01 paged-status pic xx.
01 sized-status pic xx.
01 page-size pic 99 value 0.
01 foot-size pic 99 value 3.
01 n pic 99.
01 skip pic s9v9 value 2.7.
01 counter-copy pic z9.
procedure division.
    display "before open " linage-counter in paged.
    open output paged.
    display "open " paged-status " " linage-counter of paged.
    perform varying n from 1 by 1 until n > 9
        move n to paged-line
        write paged-line at end-of-page
                display "eop " n " " linage-counter of paged
            not at end-of-page
                display "ok " n " " linage-counter of paged
        end-write
    end-perform.
    write paged-line after advancing skip lines.
    move linage-counter of paged to counter-copy.
    display "skip [" counter-copy "]".
    write paged-line before advancing page.
    write paged-line after to-top.
    write paged-line after advancing channel-1 at eop display "never".
    write paged-line after advancing 0 lines.
    close paged.
    display "closed " linage-counter of paged.

    move 4 to page-size.
    open output sized.
    display "sized open " sized-status " " linage-counter of sized.
    move "A" to sized-other.
    write sized-other in sized
        not at eop display "sized ok " linage-counter of sized.
    move 2 to page-size foot-size.
    perform 5 times
        write sized-line from "B" eop display "sized eop " linage-counter of sized
    end-perform.
    move 0 to page-size.
    perform 4 times
        write sized-line from "C" after 2
        display "sized " sized-status " " linage-counter of sized
    end-perform.
    close sized.
    display "sized close " sized-status.

    open output plain.
    move "first" to plain-line.
    write plain-line after advancing 2 lines.
    move "second" to plain-line.
    write plain-line before advancing 0 lines.
    move "third" to plain-line.
    write plain-line after advancing page.
    close plain.
    stop run.
