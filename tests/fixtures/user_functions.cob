       IDENTIFICATION DIVISION.
       FUNCTION-ID. FACT.
      * FUNCTION-ID : activation recursive, LOCAL-STORAGE, RETURNING
      * alloue a chaque activation.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  CALLS      PIC 99 VALUE 0.
       01  TMP        PIC 9(6).
       LOCAL-STORAGE SECTION.
       01  PREV       PIC 9(6).
       01  NXT        PIC 99.
       LINKAGE SECTION.
       01  N          PIC 99.
       01  RESULT     PIC 9(6).
       PROCEDURE DIVISION USING N RETURNING RESULT.
           ADD 1 TO CALLS
           IF N < 2
              MOVE 1 TO RESULT
           ELSE
              SUBTRACT 1 FROM N GIVING NXT
              MOVE FUNCTION FACT (NXT) TO TMP
              MOVE TMP TO PREV
              MULTIPLY N BY PREV GIVING RESULT
           END-IF
           GOBACK.
       END FUNCTION FACT.

       IDENTIFICATION DIVISION.
       FUNCTION-ID. ECHO-IT AS "ECHOF".
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       77  LEN        USAGE BINARY-LONG.
       LINKAGE SECTION.
       01  ARG        PIC X ANY LENGTH.
       01  OUT.
           05  FILLER PIC X OCCURS 0 TO 50 DEPENDING ON LEN.
       PROCEDURE DIVISION USING ARG RETURNING OUT.
           MOVE FUNCTION LENGTH (ARG) TO LEN
           MOVE ARG TO OUT.
       END FUNCTION ECHO-IT.

       IDENTIFICATION DIVISION.
       FUNCTION-ID. HALF.
       DATA DIVISION.
       LINKAGE SECTION.
       01  X          PIC S9(3)V9.
       01  Y          PIC S9(3)V99.
       PROCEDURE DIVISION USING X RETURNING Y.
           DIVIDE X BY 2 GIVING Y.
       END FUNCTION HALF.

       IDENTIFICATION DIVISION.
       PROGRAM-ID. FNUSER.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION FACT
           FUNCTION ECHOF
           FUNCTION HALF.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  K          PIC 99 VALUE 6.
       01  V          PIC S9(3)V9 VALUE -12.5.
       01  W          PIC X(12) VALUE "hello world".
       01  T          PIC 9(6).
       PROCEDURE DIVISION.
           DISPLAY FUNCTION FACT (K) "|" FACT (05) "|" FACT (01)
           COMPUTE T = FACT (K) + 1
           DISPLAY T
           DISPLAY "[" ECHOF ("abc") "]" FUNCTION LENGTH (ECHOF (W))
                   "[" ECHOF (W) (1:5) "]"
           IF ECHOF ("abc") = "abc"
              DISPLAY "equal"
           END-IF
           DISPLAY HALF (V) "|" FUNCTION HALF (V)
           MOVE HALF (V) TO V
           DISPLAY V
           STOP RUN.
       END PROGRAM FNUSER.
