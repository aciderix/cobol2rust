*> Words starting with digits, literals starting with a point, V-leading
*> numeric pictures, PIC A and ASCENDING KEY metadata.
identification division.
program-id. lexical-forms.
data division.
working-storage section.
01 3-dimension-tbl.
   02 2pos-num pic 99 value 42.
   02 entry-a occurs 3 times ascending key is item-a indexed by idx-1.
      03 item-a pic x value "Z".
77 fraction-a pic sv9(5) value .11111.
77 fraction-b pic v9(4) comp value .0625.
77 alpha-a pic a(6) value "tumble".
77 text-a pic x(6).
procedure division.
    display 2pos-num " " fraction-a " " fraction-b " [" alpha-a "]"
    compute fraction-a = fraction-a + .5
    display fraction-a
    move .25 to text-a display "[" text-a "]"
    move alpha-a to text-a
    display "[" text-a "] " item-a (2)
    if alpha-a = "tumble" display "EQ" end-if
    stop run.
