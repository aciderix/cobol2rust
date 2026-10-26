      $SET NOBOUND DIALECT(MF) NOTRUNC
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MFDIRECT.
      * MF directives ($ in the indicator area): $SET options without
      * effect, $IF / $ELSE / $END and $DISPLAY.
       PROCEDURE DIVISION.
      $IF CHARSET = 'ASCII'
           DISPLAY "ascii"
      $ELSE
           DISPLAY "other"
      $END
      $DISPLAY compile-time only
           STOP RUN.
