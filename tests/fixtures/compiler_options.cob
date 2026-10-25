       CBL APOST,NOSEQ
       PROCESS XOPTS(APOST) LIB
       CBL
      * IBM compiler options statements: pplex.l ignores the line.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBLOPT.
       PROCEDURE DIVISION.
           DISPLAY "options ignored"
           STOP RUN.
