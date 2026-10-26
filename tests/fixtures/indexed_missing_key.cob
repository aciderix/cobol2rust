*> A READ with KEY IS an item where no key of the file starts:
*> libcob's cob_findkey_attr finds no key (it compares addresses) and
*> the statement gives status 23, INVALID KEY.
identification division.
program-id. missing-key.
environment division.
input-output section.
file-control.
    select keyed-file assign to "keyed.dat" organization indexed
        access mode dynamic record key is rec-key file status fs.
data division.
file section.
fd keyed-file.
01 keyed-rec.
   02 rec-key pic x(4).
   02 rec-data pic x(6).
working-storage section.
01 fs pic xx.
01 wanted pic x(4) value "BBBB".
procedure division.
    open output keyed-file
    move "AAAA" to rec-key move "first" to rec-data write keyed-rec
    move "BBBB" to rec-key move "second" to rec-data write keyed-rec
    close keyed-file
    open input keyed-file
    move "BBBB" to rec-key
    read keyed-file key is wanted
        invalid key display "invalid with working-storage key " fs
        not invalid key display "found " rec-data
    end-read
    read keyed-file key is rec-data
        invalid key display "invalid with data field " fs
    end-read
    read keyed-file key is rec-key
        invalid key display "invalid " fs
        not invalid key display "found " rec-data " " fs
    end-read
    close keyed-file
    stop run.
