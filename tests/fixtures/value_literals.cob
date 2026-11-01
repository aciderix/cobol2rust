       IDENTIFICATION   DIVISION.
       PROGRAM-ID.      value-literals.
       DATA             DIVISION.
       WORKING-STORAGE  SECTION.
       01 X-ABCD        PIC XXX VALUE "abcd".
       01 X-SPACE       PIC XXX VALUE "abc   ".
       01 X-123         PIC XXX VALUE 123.
       01 X-12          PIC XXX VALUE 12.
       01 X-1234        PIC XXX VALUE 1234.
       01 G-1           VALUE 123.
         02 X           PIC XXX.
       01 G-3           VALUE "abcd".
         02 X           PIC XXX.
       01 G-4           VALUE 12.
         02 X           PIC XXX.
       01 B-123         PIC BXX VALUE 123.
       01 B-ABC         PIC BXX VALUE "abc".
       01 B-OVER        PIC BXX VALUE " abc".
       01 E-12          PIC 9(2) VALUE 123.
       PROCEDURE        DIVISION.
           DISPLAY "[" X-ABCD "][" X-SPACE "][" X-123 "][" X-12 "]["
               X-1234 "]"
           DISPLAY "[" G-1 "][" G-3 "][" G-4 "]"
           DISPLAY "[" B-123 "][" B-ABC "][" B-OVER "]"
           STOP RUN.
