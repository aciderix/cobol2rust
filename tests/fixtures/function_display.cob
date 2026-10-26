       IDENTIFICATION DIVISION.
       PROGRAM-ID. FNDISP.
      * DISPLAY des champs temporaires de intrinsic.c : copie de
      * l'argument (MAX, MIN, MEDIAN), cob_alloc_field, entier
      * non signe et champs DISPLAY de DATE-OF-INTEGER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 X  PIC S9(3)V99 VALUE -12.5.
       01 Y  PIC 9(5) COMP VALUE 4.
       01 Z  PIC S9(5)V9 COMP-3 VALUE -3.5.
       01 W  PIC 9(18) VALUE 999999999999999999.
       01 T  PIC S99 SIGN TRAILING SEPARATE VALUE 3.
       PROCEDURE DIVISION.
           DISPLAY FUNCTION MAX ( X Y Z ) "|" FUNCTION MIN ( X Y Z )
                   "|" FUNCTION MEDIAN ( X Y Z ) "|" FUNCTION MEAN ( T )
           DISPLAY FUNCTION MAX ( +3 ) "|" FUNCTION MAX ( .5 )
                   "|" FUNCTION MAX ( 007 ) "|" FUNCTION MAX ( 1.0 1 )
                   "|" FUNCTION MEDIAN ( 1 1.0 2 )
                   "|" FUNCTION MEDIAN ( 2 1.0 1 )
           DISPLAY FUNCTION SUM ( X Y Z ) "|" FUNCTION MEAN ( X Y Z )
                   "|" FUNCTION MIDRANGE ( X Y Z )
                   "|" FUNCTION MEDIAN ( X Y )
           DISPLAY FUNCTION SUM ( 4294967295 )
                   "|" FUNCTION SUM ( -2147483648 )
                   "|" FUNCTION SUM ( W W W W W W )
                   "|" FUNCTION SUM ( 99999999999999999999 )
           DISPLAY FUNCTION MEAN ( 0.000000001 0 )
                   "|" FUNCTION SUM ( 0.1234567890123456789 )
                   "|" FUNCTION SUM ( 1.5 1.5 ) "|" FUNCTION SUM ( 0 )
           DISPLAY FUNCTION PRESENT-VALUE ( 0.1 100 )
           DISPLAY FUNCTION SQRT ( 2 ) "|" FUNCTION SQRT ( 16 )
           DISPLAY FUNCTION ORD ( "A" ) "|" FUNCTION ORD-MAX ( X Y Z )
                   "|" FUNCTION INTEGER-OF-DATE ( 20240229 )
                   "|" FUNCTION DATE-OF-INTEGER ( 1 )
                   "|" FUNCTION DAY-OF-INTEGER ( 1 )
           DISPLAY FUNCTION PI
           DISPLAY FUNCTION E
           STOP RUN.
