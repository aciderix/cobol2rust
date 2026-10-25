identification division.
program-id. evaluate-forms.
data division.
working-storage section.
01 n pic 99 value 5.
01 m pic 9 value 2.
01 x pic x value "B".
01 k pic x value "4".
   88 low-k value "0" thru "4".
procedure division.
    perform varying n from 1 by 3 until n > 13
        evaluate n
            when 1
            when 2 display n " one or two"
            when 3 thru 7 display n " three thru seven"
            when not 10 display n " not ten"
            when other display n " other"
        end-evaluate
    end-perform
    evaluate n also x
        when 13 thru 20 also "A" display "13-20 A"
        when any also "B" thru "C" display "any B-C"
        when other display "none"
    end-evaluate
    evaluate true also m
        when n > 50 also any display "big"
        when low-k also 2 display "low k, m 2"
    end-evaluate
    evaluate false
        when n < 10 display "n not below 10"
    end-evaluate
    evaluate low-k also n > 3
        when true also false display "tf"
        when true also true display "tt"
    end-evaluate
    evaluate x
        when "A" display "A"
        when other display "other x"
    end-evaluate
    if m = 2
        evaluate m
            when 1 display "m1"
            when 2 display "m2"
    else
        display "not 2".
    evaluate m + 1 when 3 display "m + 1 = 3" end-evaluate
    evaluate n when 1 display "never" end-evaluate
    display "end".
    stop run.
