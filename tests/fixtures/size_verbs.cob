identification division.
program-id. size-verbs.
data division.
working-storage section.
01 a pic 99 value 90.
01 b pic s99 value -90.
01 c pic 9v99 value 7.77.
01 zero-a pic 9 value 0.
01 g.
 05 amount-a occurs 2 pic 99 comp-3 value 88.
procedure division.
add 9 to a on size error display 'BAD' not on size error display 'ADD-OK' end-add
add 1 to a on size error display 'ADD-OVER' end-add
display a
subtract 10 from b on size error display 'SUB-OVER' end-subtract
display b
subtract 100 from a on size error display 'BAD' not on size error display 'UNSIGNED' end-subtract
display a
multiply 100 by a giving amount-a(1) on size error display 'MUL-OVER' end-multiply
display amount-a(1)
divide zero-a into a giving amount-a(2) on size error display 'DIV-ZERO' end-divide
display amount-a(2)
divide 3 into a giving c rounded on size error display 'BAD' not on size error display 'DIV-OK' end-divide
display c
compute c rounded = 9.995 on size error
 compute a = (2 / zero-a) * 3 on size error
  display 'NESTED'
 end-compute
end-compute
display a '/' c
compute a = 1 / (1 / zero-a) on size error display 'INNER-ZERO' end-compute
compute a = -99.9 on size error display 'BAD' not on size error display 'TRUNC' end-compute
display a
perform handler-test
display 'AFTER'
stop run.
handler-test.
compute a = 100 on size error exit paragraph end-compute
display 'BAD-FALLTHROUGH'.
