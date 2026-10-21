identification division.
program-id. paragraphs.
data division.
working-storage section.
01 counter pic 99 value 0.
01 total pic 9(4) value 0.
procedure division.
    perform varying counter from 1 by 1 until counter > 5
        perform accumulate
    end-perform
    display "Somme=" total
    stop run.
accumulate.
    add counter to total.
