identification division.
program-id. invoice.
data division.
working-storage section.
01 quantity pic 9(3) value 3.
01 price pic 9(4)v99 value 19.95.
01 subtotal pic 9(6)v99 value 0.
01 tax pic 9(6)v99 value 0.
01 total pic 9(6)v99 value 0.
procedure division.
    compute subtotal = quantity * price
    compute tax rounded = subtotal * 0.20
    compute total = subtotal + tax
    display "HT=" subtotal " TVA=" tax " TTC=" total
    if total > 50
        display "Commande eligible"
    else
        display "Petite commande"
    end-if
    stop run.
