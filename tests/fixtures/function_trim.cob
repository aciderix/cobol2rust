       IDENTIFICATION DIVISION.
       PROGRAM-ID. FTRIM.
      * FUNCTION TRIM [LEADING|TRAILING] (cob_intr_trim), an all-space
      * argument giving an empty result.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A     PIC X(10) VALUE "  AB C    ".
       01 B     PIC X(6)  VALUE SPACES.
       01 N     PIC 9(4)  VALUE 12.
       01 R     PIC X(12).
       01 M     PIC 9(4).
       01 P     PIC 99    VALUE 1.
       PROCEDURE DIVISION.
           DISPLAY "[" FUNCTION TRIM(A) "]"
           DISPLAY "[" FUNCTION TRIM(A LEADING) "]"
           DISPLAY "[" FUNCTION TRIM(A, TRAILING) "]"
           DISPLAY "[" FUNCTION TRIM(B) "]"
           DISPLAY "[" FUNCTION TRIM("  lit  ") "]"
           DISPLAY "[" FUNCTION TRIM(N) "]"
           DISPLAY "[" FUNCTION TRIM(A)(2:2) "]"
           MOVE FUNCTION TRIM(A) TO R
           DISPLAY "[" R "]"
           MOVE FUNCTION TRIM(B) TO R
           DISPLAY "[" R "]"
           MOVE "  0042 " TO A
           MOVE FUNCTION TRIM(A) TO M
           DISPLAY M
           MOVE SPACES TO R
           STRING FUNCTION TRIM(A) DELIMITED BY SIZE
                  "/" DELIMITED BY SIZE
                  INTO R WITH POINTER P
           DISPLAY "[" R "] " P
           IF FUNCTION TRIM(A) = "0042"
               DISPLAY "EQUAL"
           END-IF
           IF FUNCTION TRIM(B) = SPACES
               DISPLAY "EMPTY IS SPACES"
           END-IF
           DISPLAY FUNCTION UPPER-CASE(FUNCTION TRIM("  x y "))
           STOP RUN.
