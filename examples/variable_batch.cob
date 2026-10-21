identification division.
program-id. variable-batch.
environment division.
input-output section.
file-control.
 select entries-file assign to 'amounts.txt'
  organization is line sequential.
 select report-file assign to 'summary.txt'
  organization is line sequential.
data division.
file section.
fd entries-file.
01 input-line.
 05 input-amount pic 9(6)v99.
fd report-file.
01 report-line.
 05 report-label pic x(6).
 05 report-total pic 9(4)v99.
working-storage section.
01 end-flag pic x value 'N'.
 88 end-input value 'Y'.
01 loaded-count pic 9 value 0.
01 rejected-count pic 99 value 0.
01 overflow-count pic 99 value 0.
01 total-a pic 9(4)v99 value 0.
01 batch-a.
 05 amount-a occurs 0 to 4 depending on loaded-count
  indexed by row-idx pic 9(4)v99 comp-3.
procedure division.
open input entries-file
perform until end-input
 read entries-file
  at end set end-input to true
  not at end
   if input-amount is numeric
    if loaded-count < 4
     add 1 to loaded-count
     compute amount-a(loaded-count) = input-amount
      on size error
       subtract 1 from loaded-count
       add 1 to rejected-count
     end-compute
    else
     add 1 to rejected-count
    end-if
   else
    add 1 to rejected-count
   end-if
 end-read
end-perform
close entries-file
perform varying row-idx from 1 by 1 until row-idx > loaded-count
 add amount-a(row-idx) to total-a
  on size error add 1 to overflow-count
 end-add
end-perform
open output report-file
move 'TOTAL=' to report-label
move total-a to report-total
write report-line
close report-file
display 'LOADED=' loaded-count ' REJECTED=' rejected-count
 ' OVERFLOWS=' overflow-count ' TOTAL=' total-a
stop run.
