       IDENTIFICATION DIVISION.
       PROGRAM-ID. DIGITS38.
      * Numeric items of more than 18 digits (COB_MAX_DIGITS 38):
      * DISPLAY and packed storage, arithmetic, editing, comparisons.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A    PIC S9(38) VALUE -12345678901234567890123456789012345678.
       01 B    PIC S9(31)V9(7) COMP-3 VALUE 1.5.
       01 C    PIC 9(20) VALUE 99999999999999999999.
       01 D    PIC S9(20)V99.
       01 E    PIC Z(30)9.99-.
       01 F    PIC S9(25)V9(5) COMP-3.
       01 G    PIC S9(19) SIGN LEADING SEPARATE.
       01 H    PIC 9(30).
       01 Q    PIC S9(36).
       01 R    PIC S9(10).
       01 T    PIC X(40).
       01 U    PIC -(25)9.
       01 V    PIC S9(37)V9 COMP-3.
       PROCEDURE DIVISION.
           DISPLAY A
           COMPUTE D = A / 3
           DISPLAY D
           COMPUTE D ROUNDED = A / 7
           DISPLAY D
           MOVE A TO E
           DISPLAY E
           ADD 1 TO C
           DISPLAY C
           ADD 1 TO C ON SIZE ERROR DISPLAY "SIZE C"
               NOT ON SIZE ERROR DISPLAY "OK C " C
           END-ADD
           SUBTRACT 2 FROM C
           ADD 99999999999999999999 TO C
               ON SIZE ERROR DISPLAY "SIZE C2"
           END-ADD
           DISPLAY C
           DISPLAY B
           COMPUTE F = B * 123456789012345678901.23456
           DISPLAY F
           MULTIPLY 1000000000000 BY F
               ON SIZE ERROR DISPLAY "SIZE F"
           END-MULTIPLY
           DISPLAY F
           MOVE -1234567890123456789 TO G
           DISPLAY G
           MOVE G TO H
           DISPLAY H
           DIVIDE A BY 1000000007 GIVING Q REMAINDER R
           DISPLAY Q " " R
           MOVE A TO T
           DISPLAY "[" T "]"
           MOVE Q TO U
           DISPLAY "[" U "]"
           IF A < Q DISPLAY "A < Q" END-IF
           IF C > 99999999999999999998
               DISPLAY "C BIG"
           ELSE
               DISPLAY "C SMALL"
           END-IF
           IF A = -12345678901234567890123456789012345678
               DISPLAY "A EQ"
           END-IF
           COMPUTE V = (A + 1) / 2
           DISPLAY V
           COMPUTE V = V ** 1
           DISPLAY V
           MOVE ZERO TO H
           PERFORM 5 TIMES
               COMPUTE H = H * 100 + 99
           END-PERFORM
           DISPLAY H
           STOP RUN.
