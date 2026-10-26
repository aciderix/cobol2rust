       IDENTIFICATION DIVISION.
       PROGRAM-ID. VALNEGZ.
      * VALUE -0 keeps its sign in a signed DISPLAY item (not in packed);
      * ADD/SUBTRACT of a zero int operand leaves the receiver untouched
      * (cob_add_int), a non-zero one stores a plain result.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       77 A PIC 9(01) VALUE 0.
       77 B PIC S9(01) VALUE -0.
       77 C PIC S9(03)V9 VALUE -0.0.
       77 D PIC S9(03) COMP-3 VALUE -0.
       77 DX REDEFINES D PIC X(2).
       77 E PIC S9(03) SIGN LEADING SEPARATE VALUE -0.
       77 F PIC S9(03) SIGN LEADING VALUE -000.
       77 G PIC S9(03) VALUE -.00.
       77 H PIC S9(03) VALUE -0.
       77 K PIC S9(02)V9 VALUE -0.
       PROCEDURE DIVISION.
           DISPLAY B(1:) " " C(1:) " " DX " " E(1:) " " F(1:) " " G(1:)
           DISPLAY B " " C " " E
           SUBTRACT A FROM B
           ADD 0 TO C
           ADD A TO E
           ADD 1 TO H
           SUBTRACT 0.0 FROM K
           DISPLAY B(1:) " " C(1:) " " E(1:) " " H(1:) " " K(1:)
           ADD -1 TO H
           DISPLAY H(1:)
           MOVE -0 TO B
           DISPLAY B(1:)
           STOP RUN.
