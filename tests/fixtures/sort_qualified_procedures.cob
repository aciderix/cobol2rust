      * SORT INPUT/OUTPUT PROCEDURE de paragraphes homonymes qualifiés
      * par leur section (OF / IN).
       IDENTIFICATION DIVISION.
       PROGRAM-ID. sort-qualified.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SW ASSIGN "sortwork".
       DATA DIVISION.
       FILE SECTION.
       SD SW.
       01 SW-REC PIC X(3).
       WORKING-STORAGE SECTION.
       01 I PIC 9 VALUE 0.
       01 DONE PIC X VALUE "N".
       PROCEDURE DIVISION.
       MAIN SECTION.
       START-UP.
           SORT SW ON DESCENDING KEY SW-REC
               INPUT PROCEDURE WORK OF FEED
               OUTPUT PROCEDURE IS WORK IN DRAIN
           STOP RUN.
       FEED SECTION.
       WORK.
           PERFORM VARYING I FROM 1 BY 1 UNTIL I > 4
              MOVE I TO SW-REC
              MOVE "X" TO SW-REC (2:1)
              RELEASE SW-REC
           END-PERFORM.
       DRAIN SECTION.
       WORK.
           PERFORM UNTIL DONE = "Y"
              RETURN SW AT END MOVE "Y" TO DONE
                 NOT AT END DISPLAY SW-REC
              END-RETURN
           END-PERFORM.
