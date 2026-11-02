       IDENTIFICATION DIVISION.
       PROGRAM-ID. canc.
       PROCEDURE DIVISION.
           CALL "cancr"
           CALL "cancr"
           STOP RUN.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. cancr IS RECURSIVE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 N PIC 9 VALUE 0.
       PROCEDURE DIVISION.
           ADD 1 TO N
           DISPLAY "cancr " N
           IF N = 1
              CANCEL "cancr"
              DISPLAY "after cancel " N
           END-IF
           GOBACK.
       END PROGRAM cancr.
       END PROGRAM canc.
