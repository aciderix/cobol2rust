       IDENTIFICATION DIVISION.
       PROGRAM-ID. PKTRUNC.
      * Packed receivers without SIZE ERROR (cob_decimal_get_packed):
      * high-order digits dropped, sign nibble kept, negative zero.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A  PIC S9(3) COMP-3 VALUE 998.
       01 AX REDEFINES A PIC X(2).
       01 B  PIC 9(3) COMP-3 VALUE 5.
       01 C  PIC S9(3) COMP-3 VALUE -999.
       01 CX REDEFINES C PIC X(2).
       01 D  PIC S9(5)V99 COMP-3 VALUE 12345.67.
       01 E  PIC 9(3) COMP-6 VALUE 999.
       01 F  PIC S9(4) COMP-3 VALUE 9999.
       PROCEDURE DIVISION.
           ADD 5 TO A
           DISPLAY A " " AX
           COMPUTE B = 123456
           DISPLAY B
           SUBTRACT 1 FROM C
           DISPLAY C " " CX
           COMPUTE C = -2000
           DISPLAY C " " CX
           COMPUTE D = D * 100
           DISPLAY D
           ADD 2 TO E
           DISPLAY E
           COMPUTE F = F + 12
           DISPLAY F
           MULTIPLY 1000 BY A
           DISPLAY A
           STOP RUN.
