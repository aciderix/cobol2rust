      * Programmes RECURSIVE : principal qui s'appelle lui-même,
      * programme contenu auto-appelant (RECURSIVE implicite) et
      * appelé dynamique RECURSIVE (recursive_calls/FACTR.cob).
       IDENTIFICATION DIVISION.
       PROGRAM-ID. recursive-calls IS RECURSIVE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 PASSES PIC 9 VALUE 0.
       01 N PIC 99 VALUE 5.
       01 R PIC 9(9).
       LOCAL-STORAGE SECTION.
       01 MY-PASS PIC 9.
       PROCEDURE DIVISION.
           ADD 1 TO PASSES
           MOVE PASSES TO MY-PASS
           DISPLAY "main pass " MY-PASS " params "
               NUMBER-OF-CALL-PARAMETERS
           IF PASSES > 1
              DISPLAY "main inner " MY-PASS
              GOBACK
           END-IF
           CALL "FACTR" USING N R
           DISPLAY "fact " N " = " R
           MOVE 3 TO N
           CALL "FACTR" USING N R
           DISPLAY "fact " N " = " R
           CALL "INNER"
           CALL "recursive-calls"
           DISPLAY "main back " MY-PASS " passes " PASSES
           STOP RUN.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INNER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 DEPTH PIC 9 VALUE 0.
       PROCEDURE DIVISION.
           ADD 1 TO DEPTH
           DISPLAY "inner " DEPTH
           IF DEPTH < 3
              CALL "INNER"
           END-IF
           DISPLAY "inner out " DEPTH
           SUBTRACT 1 FROM DEPTH
           GOBACK.
       END PROGRAM INNER.
       END PROGRAM recursive-calls.
