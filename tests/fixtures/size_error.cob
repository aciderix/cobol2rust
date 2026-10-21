IDENTIFICATION DIVISION.
PROGRAM-ID. arithmetic-errors.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 n pic 99 value 77.
01 packed-a pic 99 comp-3 value 77.
01 binary-a pic 99 comp value 77.
01 small-a pic 9v9 value 1.

PROCEDURE DIVISION.
compute n = 100 on size error display 'OV' not on size error display 'OK' end-compute display n
compute n = -12 on size error display 'NEG-OV' not on size error display 'NEG-OK' end-compute display n
compute n = 1 / 0 on size error display 'ZERO' end-compute display n
compute small-a rounded = 9.95 on size error display 'ROUND' end-compute display small-a
compute packed-a = -12 on size error display 'P-OV' not on size error display 'P-OK' end-compute display packed-a
compute binary-a = -12 on size error display 'B-OV' not on size error display 'B-OK' end-compute display binary-a
compute n = 123 not on size error display 'NO-OK' end-compute display n
STOP RUN.
