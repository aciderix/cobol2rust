*> Level 88 of a group with figurative and ALL values (the end-of-file
*> idiom of many batch programs): compared and SET over the group's size.
identification division.
program-id. group-condition-figurative.
environment division.
input-output section.
file-control.
    select student-file assign to "students.dat" organization line sequential.
data division.
file section.
fd student-file.
01 student-details.
   88 end-of-student-file value high-values.
   02 student-id pic x(4).
   02 student-name pic x(6).
working-storage section.
01 flags.
   88 flags-low value low-values.
   88 flags-zero value zero.
   88 flags-stars value all "*".
   88 flags-quotes value quotes.
   88 flags-space value spaces.
   02 flag-a pic x(3).
   02 flag-b pic 9(2).
procedure division.
    open input student-file
    read student-file
        at end set end-of-student-file to true
    end-read
    perform until end-of-student-file
        display student-id " " student-name
        read student-file
            at end set end-of-student-file to true
        end-read
    end-perform
    close student-file
    if student-details = high-values display "after end: high-values" end-if
    move low-values to flags
    if flags-low display "low" end-if
    set flags-zero to true
    if flags-zero display "zero " flags end-if
    set flags-stars to true
    if flags-stars display "stars " flags end-if
    set flags-quotes to true
    if flags-quotes display "quotes " flags end-if
    move "abcde" to flags
    if not flags-stars and not flags-space display "none" end-if
    set flags-space to true
    if flags-space display "space [" flags "]" end-if
    stop run.
