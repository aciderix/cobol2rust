       IDENTIFICATION DIVISION.
       PROGRAM-ID. FNISO.
      * FORMATTED-DATE/TIME/DATETIME, TEST-FORMATTED-DATETIME,
      * INTEGER-OF-FORMATTED-DATE, SECONDS-FROM-FORMATTED-TIME.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 FMT  PIC X(12) VALUE "YYYY-DDD".
       01 BAD  PIC X(10) VALUE "yyyymmdd".
       01 T    PIC 9(5)V9(3) VALUE 45296.789.
       PROCEDURE DIVISION.
           DISPLAY FUNCTION FORMATTED-DATE ( "YYYYMMDD" 150115 ) "|"
                   FUNCTION FORMATTED-DATE ( "YYYY-Www-D" 150115 ) "|"
                   FUNCTION FORMATTED-DATE ( FMT 150844 ) "|"
                   FUNCTION FORMATTED-DATE ( BAD 1 ) "|"
           DISPLAY FUNCTION FORMATTED-TIME ( "hh:mm:ss.ss" T ) "|"
                   FUNCTION FORMATTED-TIME ( "hhmmssZ" 86399 -1 ) "|"
                   FUNCTION FORMATTED-TIME ( "hhmmss+hhmm" 45296 -754 )
                   "|" FUNCTION FORMATTED-TIME ( "hhmmss+hhmm" 1 3000 )
                   "|"
           DISPLAY FUNCTION FORMATTED-DATETIME
                   ( "YYYYDDDThhmmss.sssssssssZ" 150846 0 1 ) "|"
                   FUNCTION FORMATTED-DATETIME
                   ( "YYYY-MM-DDThh:mm:ss" 1 45296 ) ( 6 : 5 ) "|"
           DISPLAY FUNCTION TEST-FORMATTED-DATETIME
                   ( "YYYYMMDD" "16010190" ) "|"
                   FUNCTION TEST-FORMATTED-DATETIME
                   ( "YYYYMMDDThhmmss" "16010101 000000" ) "|"
                   FUNCTION TEST-FORMATTED-DATETIME
                   ( "hhmmss+hhmm" "00000000001" ) "|"
                   FUNCTION TEST-FORMATTED-DATETIME
                   ( "YYYYWwwD" "2015W537" )
           DISPLAY FUNCTION INTEGER-OF-FORMATTED-DATE
                   ( "YYYY-Www-D" "2014-W01-1" ) "|"
                   FUNCTION INTEGER-OF-FORMATTED-DATE
                   ( "YYYY-MM-DDThh:mm:ss" "2013-12-30T12:34:56" ) "|"
                   FUNCTION SECONDS-FROM-FORMATTED-TIME
                   ( "hhmmss.ssss" "010203.0405" ) "|"
                   FUNCTION SECONDS-FROM-FORMATTED-TIME
                   ( "YYYYMMDDThhmmss" "16010101T010203" )
           STOP RUN.
