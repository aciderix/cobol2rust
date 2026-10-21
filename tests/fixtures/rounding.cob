identification division.
program-id. rounding-demo.
data division.
working-storage section.
01 n pic s9(5)v99 value 0.
01 whole pic s9(5) value 0.
procedure division.
    compute n rounded = 1 / 6
    display n
    compute n = 1 / 6
    display n
    compute n rounded = -1 / 6
    display n
    compute n = -1 / 6
    display n
    compute whole rounded = 2.5
    display whole
    compute whole rounded = -2.5
    display whole
    compute n = 12345.67
    display n
    stop run.
