identification division.
program-id. indexed-files.
*> INDEXED files as libcob 3.2 handles them with Berkeley DB: prime and
*> alternate keys (with duplicates in insertion order), START on a partial
*> key, READ NEXT after DELETE and REWRITE, statuses 21/22/23/43/46/47/48/49.
environment division.
input-output section.
file-control.
    select master assign to "IXMASTER" organization indexed
        access dynamic record key is m-key
        alternate record key is m-city with duplicates
        alternate record key is m-code
        file status is fs.
    select serial assign to "IXSERIAL" organization indexed
        access sequential record key is s-key file status is fs.
data division.
file section.
fd master.
01 m-rec.
   02 m-key.
      03 m-group pic x.
      03 m-number pic 99.
   02 m-city pic x(4).
   02 m-code pic 9(3).
   02 m-text pic x(6).
fd serial.
01 s-rec.
   02 s-key pic 9(3).
   02 s-text pic x(5).
working-storage section.
01 fs pic xx.
01 trace pic x(80) value spaces.
01 n pic 99.
procedure division.
main-part.
    open output master.
    perform add-record varying n from 1 by 1 until n > 6.
    move "A03" to m-key. move "LYON" to m-city. move 999 to m-code.
    write m-rec invalid key display "dup prime " fs end-write.
    move "Z99" to m-key. move "LYON" to m-city. move 102 to m-code.
    write m-rec invalid key display "dup alternate " fs end-write.
    close master.
    open input master.
    display "by city:".
    move "LYON" to m-city.
    start master key is = m-city invalid key display "no city" end-start.
    perform list-next 4 times.
    display "partial prime:".
    move "B" to m-group.
    start master key is not less than m-group invalid key display "no B" end-start.
    perform list-next 3 times.
    move 104 to m-code.
    read master key is m-code invalid key display "no code" end-read.
    display "code 104: " m-key " " fs.
    move 777 to m-code.
    read master key is m-code invalid key display "code 777 " fs end-read.
    write m-rec invalid key display "write on input " fs end-write.
    close master.
    open i-o master.
    move "A02" to m-key.
    read master invalid key display "no A02" end-read.
    delete master invalid key display "delete " fs end-delete.
    read master next record at end display "eof" end-read.
    display "after delete: " m-key " " fs.
    move "PARI" to m-city.
    rewrite m-rec invalid key display "rewrite " fs end-rewrite.
    move "PARI" to m-city.
    start master key is greater than m-city invalid key display "nothing after PARI " fs end-start.
    move "A01" to m-key.
    start master key is > m-key end-start.
    perform list-next 6 times.
    close master.
    perform serial-part.
    stop run.
add-record.
    move "A" to m-group.
    if n > 3 move "B" to m-group end-if.
    move n to m-number.
    move "LYON" to m-city.
    if n = 2 or n = 5 move "NICE" to m-city end-if.
    compute m-code = 100 + n.
    move "rec" to m-text.
    move n to m-text(4:2).
    write m-rec invalid key display "write " fs end-write.
list-next.
    read master next record
        at end display "  end " fs
        not at end display "  " m-key " " m-city " " m-code " " m-text " " fs
    end-read.
serial-part.
    open output serial.
    move 5 to s-key. move "five" to s-text. write s-rec.
    move 3 to s-key. move "three" to s-text. write s-rec.
    display "out of order: " fs.
    move 5 to s-key. write s-rec.
    display "same key: " fs.
    move 8 to s-key. move "eight" to s-text. write s-rec.
    close serial.
    open i-o serial.
    rewrite s-rec.
    display "rewrite before read: " fs.
    read serial.
    move 6 to s-key.
    rewrite s-rec.
    display "rewrite other key: " fs.
    read serial. display "next: " s-key " " fs.
    read serial. display "next: " s-key " " fs.
    read serial. display "next: " s-key " " fs.
    read serial. display "after end: " fs.
    close serial.
    open input serial.
    read serial. display "first: " s-key " " s-text " " fs.
    close serial.
