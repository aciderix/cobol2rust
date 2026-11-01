       IDENTIFICATION DIVISION.
       PROGRAM-ID. mlcomma.
      * dpc-in-data: xml (default.conf), then a FLOAT-LONG content.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES. DECIMAL-POINT IS COMMA.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  OUT1             PIC X(200).
       01  R.
           03  A            PIC S99V99 VALUE -1,5.
           03  B            PIC 99,99 VALUE 1,5.
           03  C            PIC V999 COMP-3 VALUE ,25.
       01  F                FLOAT-LONG VALUE 2.
      * Homonyms under FILLER groups are not checked for uniqueness.
       01  FDR.
           03  FR1          PIC X VALUE "a".
           03  FILLER.
               05  X        PIC X VALUE "1".
           03  FILLER.
               05  X        PIC X VALUE "2".
       PROCEDURE DIVISION.
           XML GENERATE OUT1 FROM R
           DISPLAY FUNCTION TRIM (OUT1)
           XML GENERATE OUT1 FROM R WITH ATTRIBUTES
           DISPLAY FUNCTION TRIM (OUT1)
           JSON GENERATE OUT1 FROM R
           DISPLAY FUNCTION TRIM (OUT1)
           MOVE ,75 TO C
           DISPLAY B " " C
           MOVE ,,5 TO C
           DISPLAY C
           XML GENERATE OUT1 FROM FDR
           DISPLAY FUNCTION TRIM (OUT1)
           XML GENERATE OUT1 FROM F
           DISPLAY "not reached"
           STOP RUN.
