identification division.
program-id. byte-stream.
data division.
working-storage section.
01 fname    pic x(20) value "bytes.dat".
01 fname2   pic x(20) value "copy.dat".
01 fname3   pic x(20) value '"renamed.dat"'.
01 missing  pic x(20) value "missing.dat".
01 dirname  pic x(20) value "subdir".
01 fhandle   pic x(4) comp-x.
01 offset   pic x(8) comp-x.
01 nbytes   pic x(4) comp-x.
01 flags    pic x comp-x value 0.
01 buffer   pic x(10).
01 info     pic x(16).
01 info-size redefines info.
   05 size-part pic x(8) comp-x.
   05 filler pic x(8).
01 fileinfo pic x(16).
01 cwd      pic x(512).
procedure division.
    call "CBL_CREATE_FILE" using fname 2 0 0 fhandle
    display "create " return-code
    move 0 to offset move 10 to nbytes move "0123456789" to buffer
    call "CBL_WRITE_FILE" using fhandle offset nbytes flags buffer
    display "write " return-code
    move 10 to offset move 5 to nbytes move "ABCDE" to buffer
    call "CBL_WRITE_FILE" using fhandle offset nbytes flags buffer
    call "CBL_FLUSH_FILE" using fhandle display "flush " return-code
    call "CBL_CLOSE_FILE" using fhandle display "close " return-code
    call "CBL_OPEN_FILE" using fname 1 0 0 fhandle
    display "open " return-code
    move 3 to offset move 4 to nbytes move spaces to buffer
    call "CBL_READ_FILE" using fhandle offset nbytes flags buffer
    display "read " return-code " [" buffer "]"
    move 128 to flags
    call "CBL_READ_FILE" using fhandle offset nbytes flags buffer
    display "size " return-code " " offset
    move 0 to flags move 15 to offset
    call "CBL_READ_FILE" using fhandle offset nbytes flags buffer
    display "end " return-code
    call "CBL_CLOSE_FILE" using fhandle
    call "CBL_OPEN_FILE" using missing 1 0 0 fhandle
    display "missing " return-code " " fhandle
    call "CBL_OPEN_FILE" using fname 9 0 0 fhandle
    display "mode " return-code
    call "CBL_COPY_FILE" using fname fname2 display "copy " return-code
    call "CBL_CHECK_FILE_EXIST" using fname2 info
    display "exist " return-code " " size-part
    call "CBL_CHECK_FILE_EXIST" using missing info display "absent " return-code
    call "CBL_RENAME_FILE" using fname2 fname3 display "rename " return-code
    call "C$FILEINFO" using fname3 fileinfo display "fileinfo " return-code
    call "CBL_DELETE_FILE" using fname3 display "delete " return-code
    call "CBL_DELETE_FILE" using fname3 display "delete again " return-code
    call "C$DELETE" using fname 0 display "c$delete " return-code
    call "CBL_CREATE_DIR" using dirname display "mkdir " return-code
    call "C$MAKEDIR" using dirname display "c$makedir " return-code
    call "CBL_CHANGE_DIR" using dirname display "chdir " return-code
    call "CBL_GET_CURRENT_DIR" using by value 0 by value 512 by reference cwd
    display "getcwd " return-code
    call "CBL_GET_CURRENT_DIR" using by value 1 by value 512 by reference cwd
    display "getcwd flags " return-code
    call "CBL_GET_CURRENT_DIR" using by value 0 by value 3 by reference cwd
    display "getcwd short " return-code
    move ".." to dirname
    call "CBL_CHANGE_DIR" using dirname
    move "subdir" to dirname
    call "CBL_DELETE_DIR" using dirname display "rmdir " return-code
    call "CBL_DELETE_DIR" using dirname display "rmdir again " return-code
    stop run.
