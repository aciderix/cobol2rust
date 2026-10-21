identification division.
program-id. interactive.
data division.
working-storage section.
01 customer pic x(20) value spaces.
01 quantity pic 999 value 0.
01 total pic 9(5)v99 value 0.
procedure division.
    display "Nom: " with no advancing
    accept customer
    display "Quantite: " with no advancing
    accept quantity
    compute total = quantity * 12.50
    display customer " : " total
    stop run.
