identification division.
program-id. copybook-demo.
data division.
working-storage section.
copy "amount.cpy".
procedure division.
    compute amount rounded = 10 / 3
    display amount
    stop run.
