       IDENTIFICATION DIVISION.
       PROGRAM-ID. COMP6.
      * COMP-6: unsigned packed decimal without sign nibble
      * (COB_FLAG_NO_SIGN_NIBBLE); S9 COMP-6 becomes COMP-3.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A PIC 9(3) COMP-6 VALUE 123.
       01 AX REDEFINES A PIC X(2).
       01 B PIC 9(4)V99 COMPUTATIONAL-6 VALUE 12.5.
       01 BX REDEFINES B PIC X(3).
       01 C PIC 9(5) COMP-6.
       01 CX REDEFINES C PIC X(3).
       01 D PIC S9(3) COMP-6 VALUE -7.
       01 DX REDEFINES D PIC X(2).
       01 E PIC 9(4) COMP-6.
       01 H.
          05 HX PIC X(2).
          05 H6 REDEFINES HX PIC 999 COMP-6.
          05 H3 REDEFINES HX PIC 99 COMP-3.
       PROCEDURE DIVISION.
           DISPLAY A " " B " " FUNCTION LENGTH(A) FUNCTION LENGTH(B)
           DISPLAY AX " " BX
           MOVE -45 TO C
           DISPLAY C " " CX
           COMPUTE C = A * B
           DISPLAY C " " CX
           SUBTRACT 2000 FROM C
           DISPLAY C
           DISPLAY D " " DX " " FUNCTION LENGTH(D)
           MOVE 1234 TO E
           MOVE E TO C
           DISPLAY E " " C
           IF A < E AND C = 1234 DISPLAY "COMPARE OK" END-IF
           MOVE X"1234" TO HX
           IF H6 IS NUMERIC DISPLAY "PAD 1234 NUMERIC" END-IF
           MOVE X"123F" TO HX
           IF H3 IS NUMERIC DISPLAY "PAD 123F NUMERIC" END-IF
           MOVE X"12AF" TO HX
           IF H3 IS NOT NUMERIC DISPLAY "12AF NOT NUMERIC" END-IF
           MOVE X"123A" TO HX
           IF H6 IS NOT NUMERIC DISPLAY "123A NOT NUMERIC" END-IF
           MOVE ZERO TO A
           DISPLAY A " " AX
           STOP RUN.
