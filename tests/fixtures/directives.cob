       >>DEFINE LEVEL AS 3
       >>DEFINE NAME AS "prod"
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DIRECTV.
      * Conditional compilation (pplex.l, ppparse.y): DEFINE, IF, ELIF,
      * ELSE, END-IF, nested, with the standard DEFINEs of cobc.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       >>IF LEVEL > 2
       01 MSG PIC X(10) VALUE "LEVEL>2".
       >>ELSE
       01 MSG PIC X(10) VALUE "LEVEL<=2".
       >>END-IF
       PROCEDURE DIVISION.
           DISPLAY MSG
       >>IF NAME = "test"
           DISPLAY "test build"
       >>ELIF NAME IS EQUAL TO "prod"
           DISPLAY "prod build"
         >>IF UNKNOWN IS DEFINED
           DISPLAY "never"
         >>ELSE
           DISPLAY "nested else"
         >>END-IF
       >>ELSE
           DISPLAY "other build"
       >>END-IF
       >>IF CHARSET = 'ASCII' *> standard DEFINE
           DISPLAY "ascii"
       >>END-IF
       >>DEFINE LEVEL OFF
       >>IF LEVEL NOT DEFINED
           DISPLAY "level removed"
       >>END-IF
       >>IF NAME = 3
           DISPLAY "different types compare false"
       >>END-IF
       >>DISPLAY "compile-time message"
           STOP RUN.
