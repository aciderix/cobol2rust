       IDENTIFICATION DIVISION.
       PROGRAM-ID. mlgen.
      * XML GENERATE and JSON GENERATE (mlio.c, libxml2, json-c).
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  OUT1             PIC X(400).
       01  SHORT1           PIC X(12).
       01  DECL22           PIC X(22).
       01  BIGOUT           PIC X(5000).
       01  N                PIC 9(5).
       01  I                PIC 99.
       01  Rec-Mixed.
           03  Txt          PIC X(12) VALUE 'a"b<c>&d''e'.
           03  Num          PIC S9(3)V99 VALUE -0.5.
           03  Zer          PIC 9(3) VALUE 0.
           03  Edt          PIC Z9.99-.
           03  Pck          PIC S9(5)V9 COMP-3 VALUE -123.4.
           03  Bin          PIC S9(4) COMP VALUE 42.
           03  C5           PIC 9(10) COMP-5 VALUE 5.
           03  Jst          PIC X(6) JUST.
           03  Grp.
               05  G1       PIC X VALUE "1".
               05  G2       PIC 999PP VALUE 12300.
               05  G3       PIC VPP9 VALUE 0.007.
           03  FILLER       PIC X VALUE "f".
           03  Tab          PIC XX OCCURS 2.
       01  Ix               INDEX.
       01  Small.
           03  S1           PIC X(3) VALUE "one".
           03  S2           PIC 9 VALUE 7.
       01  Attrs.
           03  A1           PIC X(4) VALUE "x".
           03  A2           PIC 99 VALUE 0.
           03  AG.
               05  A3       PIC X(3) VALUE SPACES.
               05  A4       PIC X(3) VALUE SPACES.
       01  Sticky.
           03  SG.
               05  SG1      PIC X(2) VALUE SPACES.
               05  SG2      PIC X(2) VALUE SPACES.
           03  SH           PIC X VALUE "h".
       01  Hv.
           03  H1           PIC 9(2) VALUE 0.
           03  H2           PIC X(2) VALUE SPACES.
           03  H3           PIC X(2) VALUE "ok".
       01  Big.
           03  BX           PIC X(4500) VALUE ALL "x".
       01  Fl.
           03  F1           FLOAT-SHORT VALUE 1.
           03  F2           PIC X VALUE "y".
       01  Dup.
           03  D1           PIC X VALUE "1".
           03  D2           PIC X VALUE "2".
           03  D3           PIC X VALUE "3".
       01  Esc.
           03  E1           PIC X(12).
       01  Empty1.
           03  EG.
               05  EG1      PIC X VALUE "z".
           03  EH           PIC X VALUE "w".
       01  NSV              PIC X(30).
       01  PFX              PIC X(6).
       01  NS-TABLE.
           03  FILLER PIC X(30) VALUE "http://a.b/c?d#e".
           03  FILLER PIC X(30) VALUE "urn:x".
           03  FILLER PIC X(30) VALUE SPACES.
           03  FILLER PIC X(30) VALUE "a b".
           03  FILLER PIC X(30) VALUE "%zz".
           03  FILLER PIC X(30) VALUE "http://[::1]:80/".
           03  FILLER PIC X(30) VALUE "http://h:99999999999/".
           03  FILLER PIC X(30) VALUE "#frag".
           03  FILLER PIC X(30) VALUE "1abc:def".
           03  FILLER PIC X(30) VALUE "  lead".
       01  NS-ENTRIES REDEFINES NS-TABLE.
           03  NS-ENTRY     PIC X(30) OCCURS 10.
       01  PF-TABLE.
           03  FILLER PIC X(6) VALUE "pf".
           03  FILLER PIC X(6) VALUE "1pf".
           03  FILLER PIC X(6) VALUE SPACES.
           03  FILLER PIC X(6) VALUE "p f".
           03  FILLER PIC X(6) VALUE "_a.b-".
       01  PF-ENTRIES REDEFINES PF-TABLE.
           03  PF-ENTRY     PIC X(6) OCCURS 5.
       PROCEDURE DIVISION.
           MOVE 1.5 TO Edt
           MOVE "ab" TO Jst
           MOVE "t1" TO Tab (1)
           MOVE "t2" TO Tab (2)
           SET Ix TO 500
           XML GENERATE OUT1 FROM Rec-Mixed COUNT IN N
           DISPLAY "x1 " FUNCTION TRIM (OUT1) "|" N "|" XML-CODE
           XML GENERATE OUT1 FROM Rec-Mixed COUNT IN N
               WITH ATTRIBUTES
           DISPLAY "x2 " FUNCTION TRIM (OUT1) "|" N "|" XML-CODE
           JSON GENERATE OUT1 FROM Rec-Mixed COUNT IN N
           DISPLAY "j1 " FUNCTION TRIM (OUT1) "|" N "|" JSON-CODE
           XML GENERATE OUT1 FROM Ix
           DISPLAY "x3 " FUNCTION TRIM (OUT1)
           JSON GENERATE OUT1 FROM Ix
           DISPLAY "j2 " FUNCTION TRIM (OUT1)
      *    Control characters: hexadecimal element and attribute.
           MOVE X"01" TO S1 (2:1)
           XML GENERATE OUT1 FROM Small
           DISPLAY "x4 " FUNCTION TRIM (OUT1) "|" XML-CODE
           XML GENERATE OUT1 FROM S2
           DISPLAY "x4 " FUNCTION TRIM (OUT1) "|" XML-CODE
           MOVE X"09" TO S1 (1:1)
           MOVE X"0A" TO S1 (2:1)
           MOVE X"0D" TO S1 (3:1)
           XML GENERATE OUT1 FROM Small WITH ATTRIBUTES
           DISPLAY "x5 " FUNCTION TRIM (OUT1) "|" XML-CODE
           XML GENERATE OUT1 FROM Small
           DISPLAY "x6 " FUNCTION TRIM (OUT1) "|" XML-CODE
           MOVE X"C3A9E282AC41" TO S1
           XML GENERATE OUT1 FROM Small WITH ATTRIBUTES
           DISPLAY "x7 " FUNCTION TRIM (OUT1) "|" XML-CODE
           XML GENERATE OUT1 FROM Small
           DISPLAY "x8 " FUNCTION TRIM (OUT1) "|" XML-CODE
           MOVE X"7F" TO S1
           XML GENERATE OUT1 FROM Small
           DISPLAY "x9 " FUNCTION TRIM (OUT1) "|" XML-CODE
           XML GENERATE OUT1 FROM Small
               TYPE OF S1 IS ATTRIBUTE, S2 IS CONTENT
           DISPLAY "x10 " FUNCTION TRIM (OUT1) "|" XML-CODE
      *    JSON escapes and the NUL that ends a json-c string.
           MOVE X"080C5C2F011F7F22" TO E1
           JSON GENERATE OUT1 FROM Esc
           DISPLAY "j3 " FUNCTION TRIM (OUT1)
           MOVE "ab" TO E1
           MOVE X"00" TO E1 (3:1)
           MOVE "cd" TO E1 (4:2)
           JSON GENERATE OUT1 FROM Esc
           DISPLAY "j4 " FUNCTION TRIM (OUT1)
           MOVE X"0D0A09" TO E1
           JSON GENERATE OUT1 FROM Esc
           DISPLAY "j5 " FUNCTION TRIM (OUT1)
      *    NAME OF, duplicate keys and OMITTED.
           XML GENERATE OUT1 FROM Dup
               NAME OF D1 IS "k", D3 IS "_x.y", Dup IS "Doubles"
           DISPLAY "x11 " FUNCTION TRIM (OUT1)
           JSON GENERATE OUT1 FROM Dup
               NAME OF D1 IS "k", D3 IS "k", D1 IS "first"
           DISPLAY "j6 " FUNCTION TRIM (OUT1)
           JSON GENERATE OUT1 FROM Dup NAME OF Dup IS OMITTED
               SUPPRESS D2
           DISPLAY "j7 " FUNCTION TRIM (OUT1)
           XML GENERATE OUT1 FROM Empty1 SUPPRESS EG1
           DISPLAY "x12 " FUNCTION TRIM (OUT1)
           JSON GENERATE OUT1 FROM Empty1 SUPPRESS EG1
           DISPLAY "j8 " FUNCTION TRIM (OUT1)
      *    SUPPRESS: root attributes are never checked (cobc).
           XML GENERATE OUT1 FROM Attrs WITH ATTRIBUTES
               SUPPRESS EVERY ATTRIBUTE WHEN ZERO OR SPACE
           DISPLAY "x13 " FUNCTION TRIM (OUT1)
           XML GENERATE OUT1 FROM Attrs
               SUPPRESS EVERY NONNUMERIC ELEMENT WHEN SPACE
           DISPLAY "x14 " FUNCTION TRIM (OUT1)
           XML GENERATE OUT1 FROM Attrs
               SUPPRESS A3 WHEN LOW-VALUE A3 WHEN SPACES
                        WHEN SPACES
           DISPLAY "x15 " FUNCTION TRIM (OUT1)
           XML GENERATE OUT1 FROM Attrs
               TYPE OF A2 IS CONTENT
               SUPPRESS WHEN SPACE EVERY CONTENT WHEN ZERO
           DISPLAY "x16 " FUNCTION TRIM (OUT1)
           MOVE HIGH-VALUES TO H2
           XML GENERATE OUT1 FROM Hv
               SUPPRESS H1 WHEN ZERO H2 WHEN HIGH-VALUE OR SPACE
           DISPLAY "x17 " FUNCTION TRIM (OUT1)
      *    is_suppressed of a group without condition stays set.
           PERFORM 2 TIMES
               XML GENERATE OUT1 FROM Sticky
                   SUPPRESS EVERY ELEMENT WHEN SPACES
               DISPLAY "x18 " FUNCTION TRIM (OUT1)
               MOVE "s1" TO SG1
           END-PERFORM
      *    Namespaces and prefixes.
           PERFORM VARYING I FROM 1 BY 1 UNTIL I > 10
               MOVE NS-ENTRY (I) TO NSV
               MOVE ALL "*" TO OUT1
               XML GENERATE OUT1 FROM Small NAMESPACE NSV
               DISPLAY "x19 " I " " XML-CODE " " OUT1 (1:60)
           END-PERFORM
           MOVE "a" TO S1
           PERFORM VARYING I FROM 1 BY 1 UNTIL I > 5
               MOVE PF-ENTRY (I) TO PFX
               MOVE ALL "*" TO OUT1
               XML GENERATE OUT1 FROM Small WITH ATTRIBUTES
                   NAMESPACE "urn:n" NAMESPACE-PREFIX PFX
               DISPLAY "x20 " I " " XML-CODE " " OUT1 (1:70)
           END-PERFORM
           XML GENERATE OUT1 FROM Small NAMESPACE "http://x/"
               NAMESPACE-PREFIX "pp"
           DISPLAY "x21 " FUNCTION TRIM (OUT1) "|" XML-CODE
      *    Too small receiving items, COUNT IN and the handlers.
           XML GENERATE SHORT1 FROM Small COUNT IN N
               ON EXCEPTION DISPLAY "x22 exception " SHORT1 "|" N
                   "|" XML-CODE
               NOT ON EXCEPTION DISPLAY "x22 no exception"
           END-XML
           XML GENERATE DECL22 FROM Small COUNT IN N
               WITH XML-DECLARATION
               ON EXCEPTION DISPLAY "x23 " DECL22 "|" N "|" XML-CODE
           END-XML
           JSON GENERATE SHORT1 FROM Small COUNT IN N
               NOT ON EXCEPTION DISPLAY "j9 no exception"
               ON EXCEPTION DISPLAY "j9 " SHORT1 "|" N "|" JSON-CODE
           END-JSON
           JSON GENERATE OUT1 FROM Small
               ON EXCEPTION DISPLAY "j10 exception"
               NOT ON EXCEPTION DISPLAY "j10 " FUNCTION TRIM (OUT1)
                   NOT ON EXCEPTION DISPLAY "j10 display"
           END-JSON
           XML GENERATE BIGOUT FROM Big COUNT IN N
           DISPLAY "x24 " N "|" BIGOUT (4495:20) "|" XML-CODE
           JSON GENERATE BIGOUT FROM Big COUNT IN N
           DISPLAY "j11 " N "|" BIGOUT (4495:20) "|" JSON-CODE
           XML GENERATE OUT1 FROM Fl WITH ATTRIBUTES
           DISPLAY "x25 " FUNCTION TRIM (OUT1) "|" XML-CODE
           IF "ab"- "cd" = "abcd"
               DISPLAY "concatenated"
           END-IF
           STOP RUN.
