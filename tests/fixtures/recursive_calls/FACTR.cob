       IDENTIFICATION DIVISION.
       PROGRAM-ID. FACTR IS RECURSIVE.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT TRACE-FILE ASSIGN TO "factr.txt"
               ORGANIZATION LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD TRACE-FILE.
       01 TRACE-LINE PIC X(30).
       WORKING-STORAGE SECTION.
       01 DEPTH PIC 99 VALUE 0.
       01 CALLS PIC 99 VALUE 0.
       LOCAL-STORAGE SECTION.
       01 M PIC 99.
       01 S PIC 9(9).
       01 MINE PIC 99 VALUE 77.
       01 ARGS PIC 9.
       LINKAGE SECTION.
       01 K PIC 99.
       01 OUT PIC 9(9).
       PROCEDURE DIVISION USING K OUT.
           ADD 1 TO DEPTH CALLS
           MOVE NUMBER-OF-CALL-PARAMETERS TO ARGS
           IF DEPTH = 1
              OPEN OUTPUT TRACE-FILE
           END-IF
           MOVE DEPTH TO MINE
           DISPLAY "enter " K " depth " DEPTH " mine " MINE
               " args " ARGS
           IF K <= 1
              MOVE 1 TO OUT
           ELSE
              PERFORM RECURSE
              COMPUTE OUT = K * S
           END-IF
           MOVE SPACES TO TRACE-LINE
           STRING "depth " DEPTH " k " K " out " OUT
               DELIMITED BY SIZE INTO TRACE-LINE
           WRITE TRACE-LINE
           DISPLAY "leave " K " mine " MINE " args " ARGS
               " calls " CALLS
           IF DEPTH = 1
              CLOSE TRACE-FILE
           END-IF
           SUBTRACT 1 FROM DEPTH
           GOBACK.
       RECURSE.
           SUBTRACT 1 FROM K GIVING M
           CALL "FACTR" USING M S OMITTED
           DISPLAY "back " K " M " M.
