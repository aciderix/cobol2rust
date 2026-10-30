identification division.
program-id. start-previous.
environment division.
input-output section.
file-control.
    select indexed-file assign "start-previous-idx.dat" organization indexed
        access dynamic record key prime-key
        alternate record key alt-key with duplicates
        status fs.
    select relative-file assign "start-previous-rel.dat" organization relative
        access dynamic relative key slot status rs.
data division.
file section.
fd indexed-file.
01 indexed-record.
   05 prime-key pic x(3).
   05 alt-key pic x(2).
   05 payload pic x(3).
fd relative-file.
01 relative-record pic x(2).
working-storage section.
01 fs pic xx.
01 rs pic xx.
01 slot pic 99.
01 i pic 99.
01 n pic 9.
01 keys-text pic x(24) value "A01B02B03C04D05E06F07G08".
01 alts-text pic x(16) value "XAXBXBXCXCXCXDZZ".
procedure division.
    open output indexed-file
    perform varying i from 1 by 1 until i > 8
        move keys-text(i * 3 - 2:3) to prime-key
        move alts-text(i * 2 - 1:2) to alt-key
        move i to payload
        write indexed-record
    end-perform
    close indexed-file
    open input indexed-file
    read indexed-file previous display "after open " fs
    move "C04" to prime-key
    start indexed-file key < prime-key perform show
    read indexed-file previous perform show
    read indexed-file previous perform show
    read indexed-file previous perform show
    read indexed-file previous perform show
    read indexed-file next perform show
    move "C" to prime-key
    start indexed-file key <= prime-key perform show
    move "C99" to prime-key
    start indexed-file key not > prime-key perform show
    start indexed-file key is less than or equal to prime-key perform show
    move "B" to prime-key
    move 1 to n
    start indexed-file key >= prime-key with length n perform show
    move 0 to n
    start indexed-file key = prime-key with size n perform show
    start indexed-file first perform show
    read indexed-file previous perform show
    start indexed-file last perform show
    read indexed-file next perform show
    read indexed-file previous perform show
    move "XC" to alt-key
    start indexed-file key <= alt-key perform show
    read indexed-file previous perform show
    read indexed-file previous perform show
    read indexed-file next perform show
    move "XB" to alt-key
    start indexed-file key < alt-key perform show
    read indexed-file previous perform show
    move "ZZ" to alt-key
    start indexed-file key > alt-key perform show
    move "XC" to alt-key
    start indexed-file key not < alt-key perform show
    start indexed-file key not >= alt-key perform show
    start indexed-file key not <= alt-key perform show
    close indexed-file
    open output relative-file
    perform varying i from 1 by 1 until i > 9
        if i not = 3 and i not = 6
            move i to slot
            move i to relative-record
            write relative-record
        end-if
    end-perform
    close relative-file
    open input relative-file
    move 20 to slot
    start relative-file key < slot perform show-relative
    move 6 to slot
    start relative-file key <= slot perform show-relative
    read relative-file next perform show-relative
    read relative-file previous perform show-relative
    move 1 to slot
    start relative-file key < slot perform show-relative
    start relative-file first perform show-relative
    read relative-file previous perform show-relative
    read relative-file next perform show-relative
    read relative-file previous perform show-relative
    read relative-file previous perform show-relative
    start relative-file last perform show-relative
    read relative-file previous perform show-relative
    read relative-file previous perform show-relative
    read relative-file previous perform show-relative
    read relative-file previous perform show-relative
    read relative-file previous perform show-relative
    read relative-file previous perform show-relative
    close relative-file
    stop run.
show.
    display fs " [" indexed-record "]".
show-relative.
    display rs " [" relative-record "] " slot.
