identification division.
program-id. storage-demo.
data division.
working-storage section.
01 packed-value pic s9(6)v99 comp-3 value -12.50.
01 binary-value pic 9(4) usage is binary value 123.
01 another-value pic s9(4) value 21 computational.
01 text-value pic x(6) value "SPACES".
procedure division.
    add 0.25 to packed-value
    multiply 2 by binary-value
    subtract 2 from another-value
    display packed-value "/" binary-value "/" another-value
    display "[" text-value "]"
    stop run.
