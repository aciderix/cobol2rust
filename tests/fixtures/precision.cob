identification division.
program-id. precision-demo.
data division.
working-storage section.
01 amount pic s9(12)v9(6) value 0.
01 other-amount pic s9(12)v9(6) value 0.
01 whole pic 9(18) value 0.
procedure division.
    compute amount = 999999999999.999999
    display amount
    compute amount = amount - 999999999999.999998
    display amount
    compute amount rounded = 2 / 7
    display amount
    compute amount rounded = -2 / 7
    display amount
    compute amount = (1 / 3) * 3
    display amount
    compute amount = 12.345678 / 0.000001
    display amount
    compute amount rounded = (123456789.123456 * 0.000123) / 3.141592
    display amount
    compute whole = 999999999999999999
    display whole
    move 0.1234567 to amount other-amount
    display amount "/" other-amount
    stop run.
