      *> EXIT SECTION outside a SECTION: cobc's implicit "MAIN SECTION" ends
      *> before the first SECTION, where execution continues (a PERFORM of
      *> the paragraph never returns).
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EXITIMPL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 PASSES PIC 9 VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "start"
           PERFORM PAR1
           DISPLAY "after perform".
       PAR1.
           ADD 1 TO PASSES
           DISPLAY "PAR1 " PASSES.
           EXIT SECTION.
       PAR2.
           DISPLAY "PAR2".
       LATER SECTION.
       LATER-PARA.
           DISPLAY "LATER " PASSES.
           STOP RUN.
