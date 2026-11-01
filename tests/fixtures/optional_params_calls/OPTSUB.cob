       IDENTIFICATION DIVISION.
       PROGRAM-ID. OPTSUB.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 Z PIC X(3) VALUE "ZZZ".
       LINKAGE SECTION.
       01 L1 PIC X(3).
       01 L2 PIC X(3).
       01 L3 PIC 9(2).
       PROCEDURE DIVISION USING L1 OPTIONAL L2
           BY REFERENCE OPTIONAL L3.
           DISPLAY "sub " NUMBER-OF-CALL-PARAMETERS " " L1
               WITH NO ADVANCING
           IF L2 OMITTED
              DISPLAY " L2 omitted" WITH NO ADVANCING
           ELSE
              DISPLAY " " L2 WITH NO ADVANCING
           END-IF
           IF L3 IS NOT OMITTED
              ADD 1 TO L3
              DISPLAY " " L3 WITH NO ADVANCING
           END-IF
           IF L2 OMITTED AND L3 OMITTED
              DISPLAY " none" WITH NO ADVANCING
           END-IF
           DISPLAY "."
           GOBACK.
       ENTRY "OPTENT" USING L1 L2.
           DISPLAY "ent " NUMBER-OF-CALL-PARAMETERS WITH NO ADVANCING
           IF L2 OMITTED
              SET ADDRESS OF L2 TO ADDRESS OF Z
           END-IF
           DISPLAY " " L1 " " L2
           GOBACK.
