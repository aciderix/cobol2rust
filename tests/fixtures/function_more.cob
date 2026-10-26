       IDENTIFICATION DIVISION.
       PROGRAM-ID. FNMORE.
      * ABS, FRACTION-PART, EXP10, CONCATENATE, SUBSTITUTE(-CASE),
      * STORED-CHAR-LENGTH, HIGHEST/LOWEST-ALGEBRAIC, TEST-DATE,
      * TEST-DAY, YEAR-TO-YYYY, DATE-TO-YYYYMMDD, DAY-TO-YYYYDDD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 X   PIC S9(4)V9(4) VALUE -1.2345.
       01 Y   PIC X(4) VALUE "defx".
       01 S   PIC X(20) VALUE "ABC111444555defxxabc".
       01 R   PIC X(30).
       01 F1  PIC S999.
       01 F2  PIC S9(4) BINARY.
       01 F3  PIC 99V9(3).
       01 F4  PIC $**,**9.99BCR.
       01 F6  USAGE BINARY-CHAR SIGNED.
       01 F7  USAGE BINARY-CHAR UNSIGNED.
       01 F8  PIC S9(3)V9 COMP-3.
       01 F10 PIC S9(4) COMP-5.
       01 F11 PIC -(4)9.99.
       PROCEDURE DIVISION.
           DISPLAY FUNCTION ABS ( X ) "|" FUNCTION ABS ( 1 )
                   "|" FUNCTION ABS ( -2.50 ) "|" FUNCTION ABS ( F8 )
           DISPLAY FUNCTION FRACTION-PART ( 3.12345 )
                   "|" FUNCTION FRACTION-PART ( -3.12345 )
                   "|" FUNCTION FRACTION-PART ( 7 )
           DISPLAY FUNCTION EXP10 ( 4 ) "|" FUNCTION EXP10 ( -3 )
                   "|" FUNCTION EXP10 ( 0 ) "|" FUNCTION EXP10 ( 2.0 )
           DISPLAY FUNCTION CONCATENATE ( Y "abc" "zz" "55" "666" )
                   "|" FUNCTION CONCAT ( Y Y ) ( 2 : 5 ) "|"
           DISPLAY FUNCTION SUBSTITUTE ( S "abc" "zz" "55" "666" ) "|"
                   FUNCTION SUBSTITUTE-CASE ( S "abc" "zz" "55" "666" )
           DISPLAY FUNCTION STORED-CHAR-LENGTH ( " some text  " )
           MOVE FUNCTION SUBSTITUTE ( S "1" "" "x" "yy" ) TO R
           DISPLAY R "|"
           DISPLAY FUNCTION HIGHEST-ALGEBRAIC ( F1 )
                   "|" FUNCTION HIGHEST-ALGEBRAIC ( F2 )
                   "|" FUNCTION HIGHEST-ALGEBRAIC ( F3 )
                   "|" FUNCTION HIGHEST-ALGEBRAIC ( F4 )
                   "|" FUNCTION HIGHEST-ALGEBRAIC ( F6 )
                   "|" FUNCTION HIGHEST-ALGEBRAIC ( F7 )
           DISPLAY FUNCTION HIGHEST-ALGEBRAIC ( F8 )
                   "|" FUNCTION HIGHEST-ALGEBRAIC ( F10 )
                   "|" FUNCTION HIGHEST-ALGEBRAIC ( F11 )
           DISPLAY FUNCTION LOWEST-ALGEBRAIC ( F1 )
                   "|" FUNCTION LOWEST-ALGEBRAIC ( F3 )
                   "|" FUNCTION LOWEST-ALGEBRAIC ( F4 )
                   "|" FUNCTION LOWEST-ALGEBRAIC ( F6 )
                   "|" FUNCTION LOWEST-ALGEBRAIC ( F10 )
                   "|" FUNCTION LOWEST-ALGEBRAIC ( F11 )
           DISPLAY FUNCTION TEST-DATE-YYYYMMDD ( 20240229 )
                   "|" FUNCTION TEST-DATE-YYYYMMDD ( 20230229 )
                   "|" FUNCTION TEST-DATE-YYYYMMDD ( 20231301 )
                   "|" FUNCTION TEST-DATE-YYYYMMDD ( 1000101 )
           DISPLAY FUNCTION TEST-DAY-YYYYDDD ( 2024366 )
                   "|" FUNCTION TEST-DAY-YYYYDDD ( 2023366 )
                   "|" FUNCTION TEST-DAY-YYYYDDD ( 1600001 )
           DISPLAY FUNCTION YEAR-TO-YYYY ( 50 2000 )
                   "|" FUNCTION YEAR-TO-YYYY ( 5 10 1995 )
                   "|" FUNCTION YEAR-TO-YYYY ( 100 )
                   "|" FUNCTION DATE-TO-YYYYMMDD ( 991231 50 2000 )
                   "|" FUNCTION DAY-TO-YYYYDDD ( 99365 10 1995 )
           STOP RUN.
