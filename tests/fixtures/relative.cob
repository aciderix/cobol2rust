*> RELATIVE files: slot format, key updates, holes, INVALID KEY, START and native quirks.
identification division. program-id. relative-files.
environment division. input-output section. file-control.
    select sf assign to "rel.dat" organization relative access sequential
        relative key sk file status ss.
    select df assign to "rel.dat" organization relative access dynamic
        relative key dk file status ds.
    select rnd-f assign to "rel.dat" organization relative access random
        relative key rk file status rs.
    select optional opt-f assign to "nothere.dat" organization relative
        access dynamic relative key ok file status os.
    select nf assign to "none.dat" organization relative access random
        relative key nk file status ns.
data division. file section.
fd sf. 01 srec pic x(4).
fd df. 01 drec pic x(4).
fd rnd-f. 01 rrec pic x(4).
fd opt-f. 01 orec pic x(4).
fd nf. 01 nrec pic x(4).
working-storage section.
01 sk pic 9 value 0. 01 dk pic 99. 01 rk pic 9(4). 01 ok pic 9. 01 nk pic 9.
01 ss pic xx. 01 ds pic xx. 01 rs pic xx. 01 os pic xx. 01 ns pic xx.
procedure division.
    open output sf display "SO " ss " " sk
    write srec from "AAAA" display "SW1 " ss " " sk
    write srec from "BBBB" display "SW2 " ss " " sk
    close sf
    open i-o rnd-f display "RO " rs
    move 5 to rk write rrec from "EEEE" display "RW5 " rs
    move 2 to rk write rrec from "XXXX" display "RW2 " rs
    move 0 to rk write rrec from "ZZZZ" display "RW0 " rs
    move 4 to rk read rnd-f display "RR4 " rs
    move 1 to rk read rnd-f display "RR1 " rs " " rrec
    move 9 to rk read rnd-f display "RR9 " rs
    move 4 to rk rewrite rrec from "DDDD" display "RRW4 " rs
    move 9 to rk rewrite rrec from "QQQQ" display "RRW9 " rs
    move 2 to rk delete rnd-f display "RD2 " rs
    move 2 to rk delete rnd-f display "RD2B " rs
    move 7 to rk delete rnd-f display "RD7 " rs
    move 2 to rk write rrec from "CCCC" invalid key display "INV" not invalid key display "RW2B " rs end-write
    move 1 to rk write rrec from "YYYY" invalid key display "RW1-INV " rs end-write
    close rnd-f
    open i-o df display "DO " ds
    perform until ds not = "00"
        read df next display "DN " ds " " dk " " drec
    end-perform
    move 3 to dk start df key is equal to dk invalid key display "ST3-INV " ds end-start
    move 4 to dk start df key = dk display "ST4 " ds read df next display "DN4 " ds " " dk " " drec
    move 2 to dk start df key > dk display "STG2 " ds read df next display "DNG " ds " " dk " " drec
    move 6 to dk start df key not < dk display "STGE6 " ds read df next display "DN6 " ds
    move 1 to dk read df display "DR1 " ds " " drec
    read df next display "DNX " ds " " dk " " drec
    rewrite drec from "bbbb" display "DRW " ds
    close df
    open input sf
    perform 6 times read sf display "SN " ss " " sk " " srec end-perform
    close sf
    open extend sf display "SE " ss
    write srec from "FFFF" display "SEW " ss " " sk
    close sf
    open input opt-f display "OO " os
    read opt-f next display "ON1 " os read opt-f next display "ON2 " os
    move 1 to ok read opt-f display "OR " os
    close opt-f
    open i-o nf display "NO " ns
    stop run.
