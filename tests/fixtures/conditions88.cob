identification division.
program-id. condition-names-demo.
data division.
working-storage section.
01 status-data.
    05 flag-a pic x value "N".
        88 enabled value "Y" when set to false is "N".
        88 disabled value "N".
    05 score pic 99 value 4.
        88 small-score values 0 thru 9.
        88 special-score values 11 22 33.
01 flags.
    05 row-a occurs 3 times.
        10 flag-b pic x value "N".
            88 active-flag value "Y" when set to false is "N".
01 raw-numeric pic xx value "AB".
01 numeric-view redefines raw-numeric pic 99.
procedure division.
    if disabled and small-score display "DEFAULTS" end-if
    set enabled to true
    if enabled and not disabled display "ENABLED" end-if
    set enabled to false
    if disabled display "DISABLED" end-if
    move 22 to score
    evaluate true
        when small-score display "SMALL"
        when special-score display "SPECIAL"
        when other display "OTHER"
    end-evaluate
    set active-flag(2) to true
    if active-flag(2) and not active-flag(1) display "TABLE-88" end-if
    set active-flag(2) to false
    display "FLAGS=[" flags "]"
    if numeric-view is not numeric display "INVALID-DATA" end-if
    move "42" to raw-numeric
    if numeric-view is numeric display "NUMBER=" numeric-view end-if
    set small-score to true
    display "SET-RANGE=" score
    stop run.
