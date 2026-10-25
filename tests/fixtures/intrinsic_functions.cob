identification division.
program-id. intrinsic-functions.
data division.
working-storage section.
01 a pic s9(4)v99 value -12.75.
01 b pic 9(3) value 7.
01 r pic s9(9)v9(6).
01 t pic x(6) value "Hello1".
01 u pic x(6).
01 n pic s9(9).
01 d pic 9(8).
01 tab. 05 e pic 9(2) occurs 4.
procedure division.
    move 10 to e(1) move 3 to e(2) move 25 to e(3) move 3 to e(4)
    compute r = function integer(a) display r
    compute r = function integer-part(a) display r
    compute r = function mod(-11 5) display r
    compute r = function rem(-11, 5) display r
    compute r = function mod(11.5 2) display r
    compute r = function factorial(b) display r
    compute r = function sum(a b 1.5) display r
    compute r = function mean(e(1) e(2) e(3) e(4)) display r
    compute r = function median(e(1) e(2) e(3) e(4)) display r
    compute r = function median(4 1 9) display r
    compute r = function midrange(e(1) e(2) e(3)) display r
    compute r = function range(e(1) e(2) e(3) e(4)) display r
    compute r = function variance(e(1) e(2) e(3) e(4)) display r
    compute r = function max(a b 3.5) display r
    compute r = function min(a, b, 3.5) display r
    compute r = function ord-max(e(1) e(2) e(3) e(4)) display r
    compute r = function ord-min(e(1) e(2) e(3) e(4)) display r
    compute r = function annuity(0.05 10) display r
    compute r = function annuity(0 4) display r
    compute r = function present-value(0.1 100 200) display r
    compute r = function max(a * 2, (b + 1) / 3, 4 - 1) display r
    compute r = function length(t) + function length("abc") display r
    move function upper-case(t) to u display u
    move function lower-case(t) to u display u
    move function reverse(t) to u display u
    move function char(66) to u display u
    compute n = function ord("A") display n
    compute n = function integer-of-date(20000301) display n
    compute d = function date-of-integer(n) display d
    compute n = function integer-of-day(2000061) display n
    compute d = function day-of-integer(n) display d
    compute r = function numval(" -12.50 ") display r
    compute r = function numval("3.5CR") display r
    compute r = function numval-c("$1,234.5") display r
    if function max("ab" "b" "a") = "b" display "maxtext" end-if
    if function ord(function char(2)) = 2 display "ord2" end-if
    compute r = function length(function lower-case("GIZZARD")) + 2 display r
    compute r = function numval-c("EUR5", "EUR") display r
    compute r = function numval-c(" $5 ", "$") display r
    if function integer(4.578) = 4 display "int4" end-if
    evaluate function mod(7 3) when 1 display "mod1" end-evaluate
    stop run.
