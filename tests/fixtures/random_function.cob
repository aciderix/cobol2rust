identification division.
program-id. random-function.
data division.
working-storage section.
01 v pic 9v9(17).
01 k pic 9(5).
01 big pic 9(18) value 123456789012345678.
procedure division.
    compute v = function random(0). display v.
    compute v = function random(1). display v.
    perform 5 times compute v = function random display v end-perform.
    compute v = function random(3). display v.
    compute v = function random(42). display v.
    perform varying k from 100 by 997 until k > 9000
        compute v = function random(k) display k " " v
        compute v = function random display v
    end-perform.
    compute v = function random(big). display v.
    compute v = function random(1.9). display v.
    stop run.
