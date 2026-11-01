      * Paramètres facultatifs : PROCEDURE DIVISION USING OPTIONAL,
      * registre NUMBER-OF-CALL-PARAMETERS, condition [NOT] OMITTED.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. optional-params.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A PIC X(3) VALUE "AAA".
       01 B PIC X(3) VALUE "BBB".
       01 CC PIC 9(2) VALUE 12.
       01 N PIC S9(4).
       01 BX PIC X BASED.
       PROCEDURE DIVISION.
           DISPLAY "main " NUMBER-OF-CALL-PARAMETERS
           IF BX OMITTED DISPLAY "BX omitted" END-IF
           ALLOCATE BX
           IF BX IS NOT OMITTED DISPLAY "BX allocated" END-IF
           IF A OMITTED OR B OMITTED
              DISPLAY "?"
           ELSE
              DISPLAY "A B"
           END-IF
           CALL "OPTSUB" USING A B CC
           CALL "OPTSUB" USING A OMITTED CC
           CALL "OPTSUB" USING A B
           CALL "OPTSUB" USING A
           CALL "OPTSUB" USING A OMITTED
           CALL "OPTSUB" USING A OMITTED OMITTED
           CALL "OPTENT" USING A
           CALL "OPTENT" USING A B
           CALL "INNER"
           CALL "INNER" USING CC
           MOVE NUMBER-OF-CALL-PARAMETERS TO N
           DISPLAY "main " N " " CC
           STOP RUN.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INNER.
       DATA DIVISION.
       LINKAGE SECTION.
       01 P PIC 9(2).
       PROCEDURE DIVISION USING OPTIONAL P.
           DISPLAY "inner " NUMBER-OF-CALL-PARAMETERS
           IF NOT P OMITTED
              ADD 1 TO P
              DISPLAY "inner " P
           END-IF
           GOBACK.
       END PROGRAM INNER.
       END PROGRAM optional-params.
