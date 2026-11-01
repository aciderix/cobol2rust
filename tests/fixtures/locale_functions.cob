      * Fonctions de locale de libcob (localeconv, strcoll, nl_langinfo,
      * strftime) après la locale de cob_init.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. locale-functions.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 D PIC X(8) VALUE "19630302".
       01 N PIC 9(8) VALUE 20261101.
       01 L PIC X(10) VALUE "POSIX".
       PROCEDURE DIVISION.
           DISPLAY "[" FUNCTION CURRENCY-SYMBOL "]["
               FUNCTION NUMERIC-DECIMAL-POINT "]["
               FUNCTION NUMERIC-THOUSANDS-SEPARATOR "]["
               FUNCTION MONETARY-DECIMAL-POINT "]["
               FUNCTION MONETARY-THOUSANDS-SEPARATOR "]"
           DISPLAY FUNCTION LOCALE-COMPARE ("A", "B")
               FUNCTION LOCALE-COMPARE ("B", "A")
               FUNCTION LOCALE-COMPARE ("A  ", "A")
               FUNCTION LOCALE-COMPARE ("a", "B")
               FUNCTION LOCALE-COMPARE ("a", "B", L)
           DISPLAY FUNCTION LOCALE-DATE (D) " "
               FUNCTION LOCALE-DATE (N) " "
               FUNCTION LOCALE-DATE (D, L) " "
               FUNCTION LOCALE-DATE (D) (1:2)
           DISPLAY "[" FUNCTION LOCALE-DATE ("1963023X") "]"
           DISPLAY FUNCTION EXCEPTION-STATUS
           DISPLAY FUNCTION LOCALE-TIME ("233012") " "
               FUNCTION LOCALE-TIME (240000) " "
               FUNCTION LOCALE-TIME-FROM-SECONDS (33012) " "
               FUNCTION LOCALE-TIME-FROM-SECONDS (86400, L)
           DISPLAY "[" FUNCTION LOCALE-TIME (236000) "]"
           DISPLAY FUNCTION EXCEPTION-STATUS
           DISPLAY "[" FUNCTION LOCALE-TIME-FROM-SECONDS ("33012") "]"
           DISPLAY "[" FUNCTION LOCALE-COMPARE ("A", "B", SPACES) "]"
           DISPLAY FUNCTION EXCEPTION-STATUS
           STOP RUN.
