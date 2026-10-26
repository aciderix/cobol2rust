       IDENTIFICATION DIVISION.
       PROGRAM-ID. CONST78.
      * Level 78 and 01 CONSTANT items: cb_add_78 substitutes the value
      * at each later use of the name.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       78 MAX-SUB      VALUE 6.
       78 TITLE-TEXT   VALUE "Report".
       78 NEG-ONE      VALUE -1.
       78 SAME-PREC    VALUE 2 + 3 * 4.
       78 DIVIDED      VALUE 7 / 2.
       78 SCALED       VALUE 1.5 * 3.
       78 PARENS       VALUE 2 * (3 + 4).
       78 STAR         VALUE ALL "*".
       78 BLANKS       VALUE SPACES.
       78 HEXA         VALUE X"414243".
       01 NORMAL-PREC  CONSTANT AS 2 + 3 * 4.
       01 TEXT-CONST   CONSTANT "abc".
       78 NAME-LEN     VALUE 8.
       01 TBL.
          05 ELT PIC 9(2) OCCURS MAX-SUB.
          78 INNER     VALUE 3.
          05 AFTER-78 PIC X(INNER) VALUE TEXT-CONST.
       01 NAME-FIELD   PIC X(NAME-LEN) VALUE TITLE-TEXT.
       01 SIGNED-N     PIC S9(3) VALUE NEG-ONE.
       01 LINE-OUT     PIC X(10).
       01 I            PIC 99.
       PROCEDURE DIVISION.
           DISPLAY TITLE-TEXT " " MAX-SUB " " NEG-ONE " " -1.50 " " +2
           DISPLAY SAME-PREC " " DIVIDED " " SCALED " " PARENS
           DISPLAY NORMAL-PREC " " TEXT-CONST " " HEXA
           DISPLAY "[" NAME-FIELD "] " SIGNED-N " [" AFTER-78 "]"
           MOVE STAR TO LINE-OUT
           DISPLAY LINE-OUT
           MOVE BLANKS TO LINE-OUT
           DISPLAY "[" LINE-OUT "]"
           PERFORM VARYING I FROM 1 BY 1 UNTIL I > MAX-SUB
               COMPUTE ELT (I) = I * MAX-SUB + NEG-ONE
           END-PERFORM
           DISPLAY TBL
           IF ELT (MAX-SUB) = MAX-SUB * MAX-SUB - 1
               DISPLAY "LAST OK"
           END-IF
           DISPLAY LENGTH OF TBL
           STOP RUN.
