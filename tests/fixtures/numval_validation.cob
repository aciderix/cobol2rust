identification division.
program-id. numval-validation.
data division.
working-storage section.
01 amount-a pic s9(9)v9(6).
procedure division.
    display "VALID:" function test-numval("  +12.30 ")
    display "POSITION:" function test-numval("12 34")
        ":" function test-numval("12cr")
    display "CURRENCY:" function test-numval-c("$1,234.50CR")
        ":" function test-numval-c("E12.30", "E")
        ":" function test-numval-c("EUR12.30", "EUR")
    display "EXPONENT:" function test-numval-f("1E+2")
        ":" function test-numval-f("1E2")
        ":" function test-numval-f("1E+00002")
    compute amount-a = function numval-f("1.25E+2")
        + function numval-f("1.25E-2")
    display "SUM:" amount-a
    move function numval-f("1x2E+1") to amount-a
    display "CONVERT:" amount-a
    display "DIRECT:" function numval-f("1.25E+2")
    stop run.
