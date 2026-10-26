       IDENTIFICATION DIVISION.
       PROGRAM-ID. COPYPART.
      * COPY REPLACING LEADING / TRAILING (is_leading_or_trailing,
      * ppecho_leading_or_trailing): one text, prefix or suffix replaced.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY PARTREC REPLACING ==:TAG:== BY ==IN1==
                              LEADING ==PFX== BY ==IN1==
                              TRAILING ==PFX== BY ==SFX==.
       COPY PARTREC REPLACING ==:TAG:== BY ==IN2==
                              LEADING "PFX-" BY "OUT-".
       PROCEDURE DIVISION.
           DISPLAY IN1-NAME " " IN1-CODE " " ITEM-SFX " " IN1 OF IN1-REC
           DISPLAY OUT-NAME " " OUT-CODE " " ITEM-PFX OF IN2-REC
           DISPLAY PFX OF IN2-REC
           STOP RUN.
