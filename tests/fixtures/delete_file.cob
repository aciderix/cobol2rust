       IDENTIFICATION DIVISION.
       PROGRAM-ID. DELFILE.
      * DELETE FILE (cob_delete_file): statuses 35, 41, 00, 38, of a
      * LINE SEQUENTIAL and an INDEXED file, and of a list of files.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT F ASSIGN TO "df.dat" ORGANIZATION LINE SEQUENTIAL
               FILE STATUS IS FS.
           SELECT G ASSIGN TO "dg.dat" ORGANIZATION INDEXED
               RECORD KEY IS G-KEY FILE STATUS IS GS.
       DATA DIVISION.
       FILE SECTION.
       FD F.
       01 F-REC PIC X(10).
       FD G.
       01 G-REC.
          05 G-KEY PIC X(4).
          05 G-DATA PIC X(6).
       WORKING-STORAGE SECTION.
       01 FS PIC XX.
       01 GS PIC XX.
       PROCEDURE DIVISION.
           DELETE FILE F
           DISPLAY "missing " FS
           OPEN OUTPUT F
           WRITE F-REC FROM "hello"
           DELETE FILE F
           DISPLAY "open " FS
           CLOSE F
           DELETE FILE F
           DISPLAY "closed " FS
           DELETE FILE F
           DISPLAY "again " FS
           OPEN OUTPUT F
           CLOSE F WITH LOCK
           DELETE FILE F
           DISPLAY "locked " FS
           OPEN OUTPUT G
           CLOSE G
           DELETE FILE G
           DISPLAY "indexed " GS
           DELETE FILE G
           DISPLAY "indexed again " GS
           DELETE FILE F G
           DISPLAY FS " " GS
           STOP RUN.
