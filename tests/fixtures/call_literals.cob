       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLLIT.
      * Literals and figurative constants as CALL arguments
      * (output_call): BY CONTENT a copy, BY REFERENCE the constant;
      * OMITTED a NULL address.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 W PIC X(3) VALUE "WWW".
       PROCEDURE DIVISION.
           CALL "LITSUB" USING BY CONTENT "AB" ZERO W "Q"
           CALL "LITSUB" USING "XY" SPACE BY CONTENT W "R"
           CALL "LITSUB" USING BY REFERENCE X"4142" QUOTE W
                               BY CONTENT LOW-VALUE
           CALL "LITSUB" USING "XY" SPACE W BY CONTENT "S"
           CALL "OMSUB" USING OMITTED "BB"
           DISPLAY W
           STOP RUN.
