      * ASSIGN forms of real programs: implicit names (dynamic assign),
      * data items read at each OPEN, devices, EXTERNAL labels, statuses.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ASSIGNNAMES.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT OUT-IMPLICIT ASSIGN TO outImplicit
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUT-EXTERNAL ASSIGN TO EXTERNAL UT-S-Extern.
           SELECT OUT-DEVICE ASSIGN TO DISK.
           SELECT Out-Own ASSIGN Out-Own.
           SELECT OUT-DISK-LIT ASSIGN TO DISK "disk-literal.dat".
           SELECT OUT-VAR ASSIGN TO WS-NAME
               FILE STATUS IS WS-STATUS.
           SELECT OUT-USING ASSIGN USING WS-OTHER OF WS-NAMES.
           SELECT IN-READER ASSIGN TO CARD-READER "reader.txt"
               FILE STATUS IS WS-STATUS.
           SELECT IN-MISSING ASSIGN TO WS-NAME
               FILE STATUS IS WS-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD OUT-IMPLICIT. 01 R-IMPLICIT PIC X(8).
       FD OUT-EXTERNAL. 01 R-EXTERNAL PIC X(8).
       FD OUT-DEVICE.   01 R-DEVICE   PIC X(8).
       FD Out-Own.      01 R-OWN      PIC X(8).
       FD OUT-DISK-LIT. 01 R-DISK-LIT PIC X(8).
       FD OUT-VAR.      01 R-VAR      PIC X(8).
       FD OUT-USING.    01 R-USING    PIC X(8).
       FD IN-READER.    01 R-READER   PIC X(8).
       FD IN-MISSING.   01 R-MISSING  PIC X(8).
       WORKING-STORAGE SECTION.
       01 WS-NAME   PIC X(30) VALUE "first-name.dat".
       01 WS-NAMES.
          05 WS-OTHER PIC X(12) VALUE "using.dat".
       01 WS-STATUS PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT OUT-IMPLICIT OUT-EXTERNAL OUT-DEVICE Out-Own
                       OUT-DISK-LIT OUT-VAR OUT-USING.
           WRITE R-IMPLICIT FROM "implicit".
           WRITE R-EXTERNAL FROM "external".
           WRITE R-DEVICE FROM "device".
           WRITE R-OWN FROM "own".
           WRITE R-DISK-LIT FROM "disklit".
           WRITE R-VAR FROM "first".
           WRITE R-USING FROM "using".
           CLOSE OUT-IMPLICIT OUT-EXTERNAL OUT-DEVICE Out-Own
                 OUT-DISK-LIT OUT-VAR OUT-USING.
      * The item is read again at the next OPEN.
           MOVE "dir/second-name.dat" TO WS-NAME.
           OPEN OUTPUT OUT-VAR.
           DISPLAY "OPEN in missing directory: " WS-STATUS.
           MOVE "second-name.dat" TO WS-NAME.
           OPEN OUTPUT OUT-VAR.
           WRITE R-VAR FROM "second".
           CLOSE OUT-VAR.
      * Blank and badly quoted names: status 31 (cob_open).
           MOVE SPACES TO WS-NAME.
           OPEN OUTPUT OUT-VAR.
           DISPLAY "OPEN blank name: " WS-STATUS.
           MOVE '"unbalanced' TO WS-NAME.
           OPEN OUTPUT OUT-VAR.
           DISPLAY "OPEN bad quote: " WS-STATUS.
           MOVE "absent.dat" TO WS-NAME.
           OPEN INPUT IN-MISSING.
           DISPLAY "OPEN absent: " WS-STATUS.
           OPEN INPUT IN-READER.
           DISPLAY "OPEN reader: " WS-STATUS.
           READ IN-READER.
           DISPLAY "READ reader: " WS-STATUS " " R-READER.
           CLOSE IN-READER.
           STOP RUN.
