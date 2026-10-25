*> Division by zero without ON SIZE ERROR: the decimal becomes NaN
*> (cob_decimal_div), the receiver keeps its value and the run goes on.
identification division.
program-id. divide-by-zero.
data division.
working-storage section.
01 numerator pic 9(4) value 1000.
01 denominator pic 9(4) value 0.
01 result pic 9(4) value 42.
01 second-res pic s9(4)v99 value -7.5.
01 zero-base pic 9 value 0.
01 exponent pic s9 value -1.
procedure division.
    divide numerator by denominator giving result
    display "divide giving: " result
    compute result = (numerator / denominator) + 1
    display "compute: " result
    compute result second-res = numerator / denominator
    display "two receivers: " result " " second-res
    divide denominator into numerator
    display "into: " numerator
    compute result = numerator / 4
    display "valid: " result
    compute result = zero-base ** exponent
    display "zero power negative: " result
    divide numerator by denominator giving result remainder second-res
    display "remainder: " result " " second-res
    stop run.
