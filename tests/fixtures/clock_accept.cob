identification division.
program-id. clock-accept.
data division.
working-storage section.
01 d6 pic 9(6).
01 d8 pic 9(8).
01 y5 pic 9(5).
01 y7 pic 9(7).
01 w pic 9.
01 t8 pic 9(8).
01 t6 pic 9(6).
01 tb pic 9(8) comp.
01 tx pic x(10).
01 wx pic xx.
01 dz pic z(5)9.
01 g. 02 g1 pic x(3). 02 g2 pic x(4).
01 cdate pic x(21).
procedure division.
    accept d6 from date. accept d8 from date yyyymmdd.
    accept y5 from day. accept y7 from day yyyyddd.
    accept w from day-of-week. accept wx from day-of-week.
    accept t8 from time. accept t6 from time. accept tb from time.
    accept tx from time. accept dz from date. accept g from date yyyymmdd.
    display d6 " " d8 " " y5 " " y7 " " w " [" wx "]".
    display t8 " " t6 " " tb " [" tx "] [" dz "] [" g "]".
    move function current-date to cdate. display cdate.
    stop run.
