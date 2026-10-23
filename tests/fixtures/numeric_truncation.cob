identification division.
program-id. numeric-truncation.
*> A numeric MOVE truncates high-order digits without SIZE ERROR.
data division.
working-storage section.
01 s-u4 pic 9(4) value 1000.
01 s-u4b pic 9(4) value 1234.
01 s-s4 pic s9(4) value -1234.
01 s-s4z pic s9(4) value -1000.
01 s-dec pic 9(3)v99 value 123.45.
01 s-sdec pic s9(3)v99 value -100.05.
01 s-bin pic s9(4) comp value -1234.
01 s-bin0 pic s9(4) comp value -1004.
01 s-pk pic s9(5) comp-3 value -12345.
01 z-b pic s9(4) comp value -1000.
01 z-p pic s9(5) comp-3 value -1000.
01 z-d pic s9(4)v9 value -1000.5.
01 z.
   05 z-rd pic s999.
   05 z-rp pic s999 comp-3.
   05 z-rp2 pic s99 comp-3.
   05 z-rb pic s99 comp.
   05 z-rv pic s9v9.
01 r.
   05 r-u3 pic 999.
   05 r-s3 pic s999.
   05 r-p3 pic s999 comp-3.
   05 r-pu2 pic 99 comp-3.
   05 r-b2 pic s99 comp.
   05 r-bu2 pic 99 comp.
   05 r-d11 pic 9v9.
   05 r-sp11 pic s9v9 comp-3.
   05 r-b4 pic s9(4) comp.
procedure division.
    move s-u4 to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11
    display "U4    " r
    move s-u4b to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11
    display "U4B   " r
    move s-s4 to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11
    display "S4    " r
    move s-s4z to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11
    display "S4Z   " r
    display r-s3 " " r-p3 " " r-sp11
    move s-dec to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11
    display "DEC   " r
    move s-sdec to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11
    display "SDEC  " r
    move s-bin to r-u3 r-s3 r-p3 r-b2 r-bu2 r-d11
    display "BIN   " r
    *> Binary to an even-digit packed receiver: the pad nibble stays zero here.
    move s-bin0 to r-pu2 r-sp11
    display "BIN0  " r
    move s-pk to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11 r-b4
    display "PK    " r
    display r-b2 " " r-bu2 " " r-b4
    move 1234 to r-u3 r-s3 r-p3 r-b2 r-bu2 r-d11
    move 1004 to r-pu2 r-sp11
    display "L1234 " r
    move -1000 to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11
    display "L-1000" r
    move -12.34 to r-u3 r-s3 r-p3 r-pu2 r-b2 r-bu2 r-d11 r-sp11
    display "L-12.3" r
    display r-s3 " " r-p3 " " r-b2 " " r-sp11
    *> Negative zeros from binary, packed and decimal senders.
    move z-b to z-rd z-rp z-rp2 z-rb z-rv
    display "ZB    " z
    move z-p to z-rd z-rp z-rp2 z-rb z-rv
    display "ZP    " z
    move z-d to z-rd z-rp z-rp2 z-rb z-rv
    display "ZD    " z
    display z-rd " " z-rp " " z-rv
    stop run.
