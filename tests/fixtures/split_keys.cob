      * Clés INDEXED composées (SOURCE IS / =) et SUPPRESS WHEN.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. split-keys.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT F ASSIGN "splitkeys.dat"
               ORGANIZATION INDEXED ACCESS DYNAMIC
               RECORD KEY IS PK SOURCE IS R-B, R-A
               ALTERNATE RECORD KEY IS AK = R-C R-A WITH DUPLICATES
                   SUPPRESS WHEN ALL "*"
               ALTERNATE RECORD KEY IS R-C WITH DUPLICATES
                   SUPPRESS WHEN ALL "*"
               FILE STATUS IS FS.
       DATA DIVISION.
       FILE SECTION.
       FD F.
       01 R.
          03 R-A PIC X(2).
          03 R-B PIC 9(2).
          03 R-C PIC X(2).
          03 R-D PIC X(4).
       WORKING-STORAGE SECTION.
       01 FS PIC XX.
       01 DONE PIC X.
       PROCEDURE DIVISION.
           OPEN OUTPUT F
           MOVE "AA01XXone " TO R  WRITE R
           MOVE "BB01XXtwo " TO R  WRITE R
           MOVE "AA02YYthr " TO R  WRITE R
           MOVE "CC01**sup " TO R  WRITE R
           MOVE "AA01ZZdup " TO R  WRITE R
           DISPLAY "dup write " FS
           CLOSE F
           OPEN I-O F
           MOVE "BB" TO R-A MOVE 01 TO R-B
           READ F KEY IS PK
              INVALID KEY DISPLAY "no BB01"
              NOT INVALID KEY DISPLAY "pk " R
           END-READ
           MOVE "XX" TO R-C MOVE LOW-VALUE TO R-A
           START F KEY >= AK
              INVALID KEY DISPLAY "no AK"
           END-START
           PERFORM LIST-AK
           MOVE "AA" TO R-A
           START F KEY >= R-A INVALID KEY DISPLAY "no key at R-A " FS
           END-START
           MOVE "AA" TO R-A MOVE 02 TO R-B
           READ F KEY IS PK END-READ
           MOVE "**" TO R-C
           REWRITE R
           DISPLAY "rewrite " FS
           MOVE "BB" TO R-A MOVE 01 TO R-B
           DELETE F
           DISPLAY "delete " FS
           MOVE LOW-VALUE TO R-C R-A
           START F KEY >= AK INVALID KEY DISPLAY "no AK" END-START
           PERFORM LIST-AK
           MOVE LOW-VALUE TO R-C
           START F KEY >= R-C INVALID KEY DISPLAY "no R-C" END-START
           PERFORM LIST-AK
           CLOSE F
           STOP RUN.
       LIST-AK.
           MOVE "N" TO DONE
           PERFORM UNTIL DONE = "Y"
              READ F NEXT AT END MOVE "Y" TO DONE
                 NOT AT END DISPLAY "ak " R
              END-READ
           END-PERFORM.
