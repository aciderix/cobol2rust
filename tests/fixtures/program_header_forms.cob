       IDENTIFICATION DIVISION.
       PROGRAM-ID. HDRFORMS.
      * PROCEDURE DIVISION CHAINING (cob_chain_setup), a sibling
      * program without IDENTIFICATION DIVISION and named AS a literal,
      * PROCEDURE DIVISION RETURNING OMITTED.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 ARG1 PIC X(5) VALUE "none".
       PROCEDURE DIVISION CHAINING ARG1.
           DISPLAY "[" ARG1 "]"
           CALL "ext-name"
           CALL "OMITRET"
           STOP RUN.
       END PROGRAM HDRFORMS.
       PROGRAM-ID. INTERNAL AS "ext-name".
       PROCEDURE DIVISION.
           DISPLAY "called by its external name"
           GOBACK.
       END PROGRAM INTERNAL.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OMITRET.
       PROCEDURE DIVISION RETURNING OMITTED.
           DISPLAY "no returning item"
           GOBACK.
       END PROGRAM OMITRET.
