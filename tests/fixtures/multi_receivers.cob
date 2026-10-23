*> Several receivers: re-read single operands, shared sums, per-receiver ROUNDED and SIZE ERROR.
identification division. program-id. multi-receivers.
data division. working-storage section.
01 x pic s99 value 1.
01 y pic s99 value 10.
01 z pic s99 value 0.
01 w pic s99 value 0.
01 r1 pic s99.
01 r2 pic s99v9.
01 big pic s99 value 95.
01 t. 02 e pic s99 occurs 3.
01 i pic 9 value 1.
01 bx pic s99 comp value 1.
01 bnby pic s99 comp value 10.
01 px pic s99 comp-3 value 3.
01 py pic s99 comp-3 value 10.
01 dx pic s9v9 value 1.5.
01 dy pic s99 value 10.
procedure division.
    move 1 to x move 10 to y add x to x y display "ADD   " x " " y
    move 1 to x move 10 to y add x 2 to x y display "ADD2  " x " " y
    move 3 to x move 10 to y subtract x from x y display "SUB   " x " " y
    move 3 to x move 10 to y multiply x by x y display "MUL   " x " " y
    move 2 to x move 10 to y divide x into x y display "DIV   " x " " y
    move 1 to x move 10 to y compute x y = x + 1 display "COMP  " x " " y
    move 1 to x move 10 to y add x to y giving z w display "GIV   " z " " w
    move 0 to r1 r2 add 1.56 to r1 rounded r2 display "RND   " r1 " " r2
    move 0 to r1 r2 add 1.56 to r1 r2 rounded display "RND2  " r1 " " r2
    move 1 to x move 95 to big move 10 to y
    add 10 to x big y on size error display "SIZE  " x " " big " " y not on size error display "NOSIZE" end-add
    move 95 to big add 1 to big x not on size error display "OK " big " " x end-add
    move 1 to i move 0 to e(1) e(2) e(3) add 1 to i e(i) display "SUBS  " i " " e(1) e(2) e(3)
    move 1 to i move 0 to e(1) e(2) e(3) compute i e(i) = 2 display "CSUB  " i " " e(1) e(2) e(3)
    move 5 to x move 10 to y subtract 1 2 from x y display "SUB2  " x " " y
    move 2 to x multiply 3 by x giving y z display "MULG  " y " " z
    move 2 to x divide x into 9 giving y z display "DIVG  " y " " z
    move 1 to x move 10 to y add x to y giving x w display "GIVA  " x " " w
    move 1 to x move 10 to y multiply x by y giving x w display "MULA  " x " " w
    add bx to bx bnby display "BIN   " bx " " bnby
    multiply px by px py display "PACK  " px " " py
    add dx to dx dy display "DEC   " dx " " dy
    move 1 to x compute x w = x + 5 display "COMPA " x " " w
    stop run.
