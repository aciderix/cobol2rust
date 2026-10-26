       IDENTIFICATION DIVISION.
       PROGRAM-ID. DISPCLS.
      * DISPLAY clauses in any order, NO ADVANCING without WITH and
      * several display atoms in one statement (parser.y display_list).
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 X PIC X(3) VALUE "ABC".
       01 N PIC 9(3) VALUE 42.
       PROCEDURE DIVISION.
           DISPLAY X NO ADVANCING
           DISPLAY X(2:1) N NO ADVANCING UPON SYSOUT
           DISPLAY "-" WITH NO ADVANCING
           DISPLAY "E1" UPON SYSERR "S1" UPON CONSOLE NO ADVANCING
           DISPLAY "T1" NO ADVANCING "T2" "T3"
           DISPLAY "U1" UPON SYSOUT
                   "U2" NO ADVANCING UPON SYSERR
           DISPLAY "END" END-DISPLAY
           STOP RUN.
