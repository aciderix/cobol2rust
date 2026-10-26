      *> Forms of real programs that cobc accepts: comment entries after
      *> PROGRAM-ID without IDENTIFICATION DIVISION, CLASS with figurative
      *> constants, an IF ended by the END-PERFORM around it, INSPECT of a
      *> function result, reference modification of a function result.
       PROGRAM-ID. scope-forms.
       AUTHOR. Somebody, with a comment entry.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
           CLASS NAME-CHARS IS "A" THRU "Z", "a" THRU "z", SPACE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 TEXT-LINE PIC X(20) VALUE "Hello World 42".
       01 VOWELS PIC 99 VALUE ZERO.
       01 OTHERS-COUNT PIC 99 VALUE ZERO.
       01 IDX PIC 99.
       01 CODE-PART PIC X(5).
       01 DIGITS-PART PIC 9(2).
       PROCEDURE DIVISION.
           IF TEXT-LINE (1:11) IS NAME-CHARS DISPLAY "name chars"
           ELSE DISPLAY "not name chars" END-IF
           INSPECT FUNCTION UPPER-CASE (TEXT-LINE)
               TALLYING VOWELS FOR ALL "A" "E" "I" "O" "U"
           DISPLAY "vowels " VOWELS
           PERFORM VARYING IDX FROM 1 BY 1 UNTIL IDX > 14
               IF TEXT-LINE (IDX:1) = "o" CONTINUE
                 ELSE IF TEXT-LINE (IDX:1) = "l" ADD 1 TO OTHERS-COUNT
               END-IF
           END-PERFORM
           DISPLAY "l count " OTHERS-COUNT
           MOVE FUNCTION UPPER-CASE (TEXT-LINE) (7:5) TO CODE-PART
           DISPLAY "[" CODE-PART "]"
           MOVE FUNCTION REVERSE (TEXT-LINE) (7:2) TO DIGITS-PART
           DISPLAY "[" DIGITS-PART "]"
           STOP RUN.
