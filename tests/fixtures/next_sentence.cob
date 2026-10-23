identification division.
program-id. next-sentence.
data division.
working-storage section.
01 n pic 9 value 0.
01 i pic 9 value 0.
procedure division.
main-para.
    move 1 to n
    if n = 1
        if n > 0 next sentence else display "never-a" end-if
        display "never-b"
    end-if
    display "never-c".
    display "s2".
    if n = 2 display "never-d" else next sentence.
    display "s3".
    evaluate n when 1 next sentence when other display "never-e" end-evaluate
    display "never-f".
    perform varying i from 1 by 1 until i > 5
        display "loop " i
        if i = 3 next sentence end-if
    end-perform
    display "never-g".
    display "after loop " i.
    perform sub-para.
    display "back".
    stop run.
sub-para.
    display "in sub"
    next sentence
    display "never-h".
    display "sub s2".
last-para.
    if n = 1 next sentence end-if display "tail"
