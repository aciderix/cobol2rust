       IDENTIFICATION DIVISION.
       PROGRAM-ID. LITSUB.
       DATA DIVISION.
       LINKAGE SECTION.
       01 A PIC X(2).
       01 B PIC X.
       01 C PIC X(3).
       01 D PIC X.
       PROCEDURE DIVISION USING A B C D.
           DISPLAY "[" A "][" B "][" C "][" D "]"
           MOVE "CCC" TO C
           MOVE "d" TO D
           GOBACK.
