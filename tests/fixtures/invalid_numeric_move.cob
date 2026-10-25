*> cb_build_move_field copies a numeric sender byte for byte when the
*> receiver has the same description, or is alphanumeric and the sender is
*> unsigned DISPLAY, without reading its digits; SORT compares numeric keys
*> with cob_numeric_cmp (integer reading below 19 digits).
identification division.
program-id. invalid-move.
environment division.
input-output section.
file-control.
    select work-file assign to "work.tmp".
data division.
file section.
sd work-file.
01 work-rec.
   02 work-key pic 9(3).
   02 work-tag pic x.
working-storage section.
01 raw pic x(3) value "5  ".
01 number-a redefines raw pic 9(3).
01 number-b pic 9(3).
01 text-a pic x(2).
01 raw-scaled pic x(4) value "1A2 ".
01 scaled redefines raw-scaled pic 99v99.
01 group-b.
   02 text-b pic x(4).
01 keys pic x(12) value "5  A12 B013C".
01 key-table redefines keys.
   02 key-entry occurs 3 pic x(4).
01 i pic 9.
procedure division.
    move number-a to number-b
    display "[" number-b "]"
    move number-a to text-a
    display "[" text-a "]"
    display "[" scaled "]"
    move scaled to group-b
    display "[" text-b "]"
    sort work-file on ascending key work-key
        input procedure is load-keys
        output procedure is show-keys
    stop run.
load-keys.
    perform varying i from 1 by 1 until i > 3
        move key-entry (i) to work-rec
        release work-rec
    end-perform.
show-keys.
    perform 3 times
        return work-file at end display "end" end-return
        display work-tag
    end-perform.
