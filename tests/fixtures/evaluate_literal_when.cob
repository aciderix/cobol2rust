       IDENTIFICATION DIVISION.
       PROGRAM-ID. EVALWHEN.
      * WHEN lines sharing one imperative statement, the following
      * WHEN starting with a literal.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 CODE-X PIC X(8).
       01 I      PIC 9.
       PROCEDURE DIVISION.
           PERFORM VARYING I FROM 1 BY 1 UNTIL I > 4
               EVALUATE I
                   WHEN 1 MOVE 'UPDATE  ' TO CODE-X
                   WHEN 2 MOVE 'BALANCE ' TO CODE-X
                   WHEN 3 MOVE 'ORDERS  ' TO CODE-X
                   WHEN OTHER MOVE 'X' TO CODE-X
               END-EVALUATE
               EVALUATE CODE-X
                   WHEN 'UPDATE  '
                       DISPLAY 'U'
                   WHEN 'BALANCE '
                   WHEN 'ORDERS  '
                       DISPLAY 'B-O ' CODE-X
                   WHEN OTHER
                       DISPLAY 'OTHER'
               END-EVALUATE
           END-PERFORM
           STOP RUN.
