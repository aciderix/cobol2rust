       IDENTIFICATION DIVISION.
       PROGRAM-ID. rnd.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT F ASSIGN "rnd.dat" ORGANIZATION RELATIVE
               ACCESS RANDOM RELATIVE KEY K FILE STATUS FS.
       DATA DIVISION.
       FILE SECTION.
       FD F.
       01 R PIC X(4).
       WORKING-STORAGE SECTION.
       01 K PIC 9(4).
       01 FS PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT F
           MOVE 2 TO K
           MOVE "ABCD" TO R
           WRITE R INVALID KEY DISPLAY "w invalid" END-WRITE
           CLOSE F
           OPEN INPUT F
           MOVE 2 TO K
           READ F AT END DISPLAY "end 2" NOT AT END DISPLAY "got " R
           END-READ
           DISPLAY FS
           MOVE 5 TO K
           READ F AT END DISPLAY "end 5" NOT AT END DISPLAY "got5 " R
           END-READ
           DISPLAY FS
           MOVE 7 TO K
           READ F INVALID KEY DISPLAY "inv 7" END-READ
           DISPLAY FS
           CLOSE F
           STOP RUN.
