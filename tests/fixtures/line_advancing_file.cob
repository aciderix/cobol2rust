       IDENTIFICATION DIVISION.
       PROGRAM-ID. LINEADV.
      * ASSIGN LINE ADVANCING FILE (flag_line_adv): LINE SEQUENTIAL, a
      * WRITE without ADVANCING is AFTER 1 LINE, no data validation.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT PRT ASSIGN TO LINE ADVANCING FILE "lineadv.txt".
           SELECT PLAIN ASSIGN TO "plain.txt"
               ORGANIZATION LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD PRT.
       01 PRT-REC PIC X(10).
       FD PLAIN.
       01 PLAIN-REC PIC X(10).
       PROCEDURE DIVISION.
           OPEN OUTPUT PRT PLAIN
           WRITE PRT-REC FROM "first"
           WRITE PRT-REC FROM "second"
           WRITE PRT-REC FROM "tab" & X"09" & "ff" & X"0C"
           WRITE PRT-REC FROM "third" AFTER ADVANCING 2 LINES
           WRITE PRT-REC FROM "fourth" BEFORE ADVANCING 1 LINE
           WRITE PLAIN-REC FROM "first"
           WRITE PLAIN-REC FROM "second"
           CLOSE PRT PLAIN
           STOP RUN.
