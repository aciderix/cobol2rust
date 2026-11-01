      * Lot 2 de constructions générales : EVALUATE à objet partiel,
      * STOP identificateur, point redondant, registre WHEN-COMPILED.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. small-constructs-2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 N PIC S9(4) VALUE ZERO.
       01 T PIC X(4).
       01 C PIC X(16).
       01 K PIC 9 VALUE 0.. *> point redondant
       .
       PROCEDURE DIVISION.
           PERFORM VARYING N FROM -2 BY 3 UNTIL N > 13
              EVALUATE N
                 WHEN 1
                    DISPLAY N " is one"
                 WHEN >= 10
                    DISPLAY N " >= 10"
                 WHEN NOT < 4
                    DISPLAY N " not < 4"
                 WHEN IS NEGATIVE
                    DISPLAY N " negative"
                 WHEN OTHER
                    DISPLAY N " other"
              END-EVALUATE
           END-PERFORM
           MOVE "12AB" TO T
           EVALUATE T (1:2) ALSO T (3:2)
              WHEN NUMERIC ALSO NOT NUMERIC
                 DISPLAY "numeric, not numeric"
              WHEN OTHER
                 DISPLAY "other"
           END-EVALUATE
           EVALUATE TRUE ALSO N
              WHEN N > 5 ALSO > 12
                 DISPLAY "both"
              WHEN ANY ALSO NOT = 13
                 DISPLAY "not 13"
              WHEN OTHER
                 DISPLAY "13"
           END-EVALUATE
           MOVE WHEN-COMPILED TO C
           INSPECT C CONVERTING "0123456789" TO "9999999999"
           DISPLAY C.
           STOP K
           DISPLAY "after stop".
           STOP RUN.
