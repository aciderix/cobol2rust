identification division.
program-id. sort-merge.
environment division.
input-output section.
file-control.
    select sd1 assign to "SORTWK1".
    select in1 assign to "SORTIN1" organization sequential.
    select in2 assign to "SORTIN2" organization sequential.
    select out1 assign to "SORTOUT1" organization sequential.
    select out2 assign to "SORTOUT2" organization line sequential.
data division.
file section.
sd sd1.
01 s-rec.
   05 s-key1 pic 9(2).
   05 s-key2 pic x(3).
   05 s-amt pic s9(3).
   05 s-tag pic x(2).
fd in1.
01 i1-rec pic x(10).
fd in2.
01 i2-rec pic x(12).
fd out1.
01 o1-rec pic x(8).
fd out2.
01 o2-rec pic x(10).
working-storage section.
01 w-rec.
   05 w-key1 pic 9(2).
   05 w-key2 pic x(3).
   05 w-amt pic s9(3).
   05 w-tag pic x(2).
01 n pic 99 value 0.
01 eof pic x value "N".
01 r pic x(10).
procedure division.
main-para.
    open output in1 in2
    move "05BBB001A1" to i1-rec write i1-rec
    move "02ZZZ00qA2" to i1-rec write i1-rec
    move "05AAA000A3" to i1-rec write i1-rec
    move "02ZZZ005A4" to i1-rec write i1-rec
    move "05BBB00rA5XX" to i2-rec write i2-rec
    move "01CCC003B6YY" to i2-rec write i2-rec
    close in1 in2
    sort sd1 on ascending key s-key1 descending key s-key2 ascending s-amt
        using in1 in2 giving out1 out2
    display "s-rec after using/giving [" s-rec "]"
    sort sd1 on descending key s-key1 s-tag
        input procedure is make-records
        output procedure is show-records thru show-end
    merge sd1 on ascending key s-key1 using in1 in2 giving out1
    open input out1
    perform until eof = "Y"
        read out1 at end move "Y" to eof not at end display "merged [" o1-rec "]" end-read
    end-perform
    close out1
    stop run.
make-records section.
mk-1.
    perform varying n from 1 by 1 until n > 5
        compute w-key1 = 10 - n * 2 + (n / 3) * 5
        move "ABC" to w-key2
        move n to w-amt
        move "T" to w-tag
        release s-rec from w-rec
    end-perform.
show-records section.
sh-1.
    return sd1 into r at end go to show-end.
    display "returned [" r "] [" s-rec "]"
    go to sh-1.
show-end.
    return sd1 at end display "end again" not at end display "more?" end-return.
