      * Lot 3 : phrases multiples de SPECIAL-NAMES, conditions de classe
      * sur les octets de tout article, GLOBAL du conteneur le plus proche.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. small-constructs-3.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
           CLASS EVEN IS "0" "2" "4" "6" "8".
           CLASS HEXA IS "0" THRU "9" "A" THRU "F".
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 X PIC X(5) GLOBAL VALUE "outer".
       01 N PIC 9(2) VALUE 24.
       01 S PIC S9(2) VALUE -24.
       01 C PIC 9(4) COMP VALUE 2.
       01 E PIC 9.99 VALUE 2.4.
       01 H PIC X(4) VALUE "1F2a".
       PROCEDURE DIVISION.
           IF N IS EVEN DISPLAY "N even" END-IF
           IF S IS EVEN DISPLAY "S even"
           ELSE DISPLAY "S not" END-IF
           IF E IS EVEN DISPLAY "E even"
           ELSE DISPLAY "E not" END-IF
           IF C IS NOT EVEN DISPLAY "C not" END-IF
           IF N IS ALPHABETIC DISPLAY "N alpha"
           ELSE DISPLAY "N not" END-IF
           IF H (1:3) IS HEXA DISPLAY "H13 hexa" END-IF
           IF H IS HEXA DISPLAY "H hexa"
           ELSE DISPLAY "H not" END-IF
           DISPLAY X
           CALL "MIDDLE"
           STOP RUN.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MIDDLE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 X PIC X(5) GLOBAL VALUE "inner".
       PROCEDURE DIVISION.
           DISPLAY X
           CALL "LEAF"
           GOBACK.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LEAF.
       PROCEDURE DIVISION.
           DISPLAY "leaf " X
           GOBACK.
       END PROGRAM LEAF.
       END PROGRAM MIDDLE.
       END PROGRAM small-constructs-3.
