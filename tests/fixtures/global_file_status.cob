      * FD GLOBAL dont FILE STATUS et RELATIVE KEY sont des articles non
      * GLOBAL du programme propriétaire, mis à jour par un contenu.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. global-file-status.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT REL-FILE ASSIGN "globrel.dat"
               ORGANIZATION RELATIVE ACCESS DYNAMIC
               RELATIVE KEY RK FILE STATUS FS.
       DATA DIVISION.
       FILE SECTION.
       FD REL-FILE GLOBAL.
       01 REL-REC PIC X(4).
       WORKING-STORAGE SECTION.
       01 KEYS.
          03 RK PIC 9(4).
          03 FS PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT REL-FILE
           MOVE 3 TO RK
           MOVE "ccc3" TO REL-REC
           WRITE REL-REC
           CLOSE REL-FILE
           OPEN I-O REL-FILE
           MOVE 9 TO RK
           CALL "READER"
           DISPLAY "after missing " FS " " RK
           MOVE 3 TO RK
           CALL "READER"
           DISPLAY "after found " FS " " RK
           CLOSE REL-FILE
           STOP RUN.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. READER.
       PROCEDURE DIVISION.
           READ REL-FILE
               INVALID KEY DISPLAY "reader: invalid"
               NOT INVALID KEY DISPLAY "reader: " REL-REC
           END-READ
           GOBACK.
       END PROGRAM READER.
       END PROGRAM global-file-status.
