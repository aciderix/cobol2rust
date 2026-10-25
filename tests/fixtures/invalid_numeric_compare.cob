*> HIGH-VALUES and LOW-VALUES in unsigned DISPLAY items: cobc picks memcmp,
*> cob_cmp_numdisp (integer reading), cob_cmp_llint (decimal reading, first
*> byte X"FF" = 10 ** size, X"00" = - 10 ** size) or cob_numeric_cmp.
identification division.
program-id. invalid-compare.
data division.
working-storage section.
01 high-key pic 9(4).
01 low-key pic 9(4).
01 other-key pic 9(4) value 9999.
01 scaled-key pic 9(2)v99.
01 wide-key pic 9(6) value 999999.
01 wide-scaled pic 9(3)v99 value 120.
procedure division.
    move high-values to high-key scaled-key
    move low-values to low-key
    if high-key = 9999 display "numdisp: high = 9999" else display "numdisp: high <> 9999" end-if
    if high-key > other-key display "memcmp: high > other" else display "memcmp: high <= other" end-if
    if high-key > wide-key display "cmp: high > wide" else display "cmp: high <= wide" end-if
    if wide-key < high-key display "numdisp: wide < high" else display "numdisp: wide >= high" end-if
    if scaled-key > 99.99 display "cmp: scaled > 99.99" else display "cmp: scaled <= 99.99" end-if
    if scaled-key > 99 display "llint: scaled > 99" else display "llint: scaled <= 99" end-if
    if low-key < 1 display "numdisp: low < 1" else display "numdisp: low >= 1" end-if
    if low-key < other-key display "memcmp: low < other" else display "memcmp: low >= other" end-if
    if low-key + 0 < 0 display "decimal: low < 0" else display "decimal: low >= 0" end-if
    if high-key + 0 > 9999 display "decimal: high > 9999" else display "decimal: high <= 9999" end-if
    if high-key > scaled-key display "cmp: high > scaled" else display "cmp: high <= scaled" end-if
    if scaled-key > wide-scaled display "cmp: scaled > wide" else display "cmp: scaled <= wide" end-if
    if 9999 < high-key display "llint: 9999 < high" else display "llint: 9999 >= high" end-if
    stop run.
