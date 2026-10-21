identification division.
program-id. storage-layout-demo.
data division.
working-storage section.
01 display-group.
    05 signed-display pic s9(4)v99 value -12.34.
    05 positive-display pic s9(3) value 21.
01 packed-group.
    05 packed-a pic s9(3) comp-3 value -15.
    05 packed-b pic 9(4) comp-3 value 1234.
01 binary-group.
    05 binary-a pic s9(3) comp value -15.
    05 binary-b pic 9(5) binary value 12345.
01 binary-raw redefines binary-group pic x(6).
procedure division.
    display display-group
    display packed-group
    display binary-group
    display binary-raw
    display signed-display "/" positive-display
    display packed-a "/" packed-b
    display binary-a "/" binary-b
    add 5 to packed-a
    add 10 to binary-a
    display packed-group
    display binary-raw
    initialize packed-group binary-group
    display packed-group
    display binary-raw
    stop run.
