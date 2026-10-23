identification division.
program-id. numeric-editing.
data division.
working-storage section.
01 e1 pic zzz,zz9.99.
01 e2 pic $$$,$$9.99.
01 e3 pic +++,++9.
01 e4 pic ----9.99.
01 e5 pic 9(3)b9(2)/99.
01 e6 pic ***,**9.99.
01 e7 pic zz9.99cr.
01 e8 pic zz9.99db.
01 e9 pic $zz9.99+.
01 e10 pic -$$$9.
01 e11 pic .9999/99999,99999,99.
01 e12 pic zzzpp.
01 e13 pic 9(4)00.
01 e14 pic zz,zzz.zz blank when zero.
01 e15 pic 999 blank when zero.
01 e16 pic $9,9b9.90+.
01 e17 pic ++++.++.
01 e18 pic z(4).z(2).
01 e19 pic *(4).*(2).
01 e20 pic -(5).
01 e21 pic 9.99-.
01 e22 pic $$$$.
01 e23 pic vpp99.
01 n pic s9(7)v9(4).
01 i pic 99.
01 vals.
   05 filler pic s9(7)v9(4) value 1234.5678.
   05 filler pic s9(7)v9(4) value -1234.5678.
   05 filler pic s9(7)v9(4) value 0.
   05 filler pic s9(7)v9(4) value 0.05.
   05 filler pic s9(7)v9(4) value -0.05.
   05 filler pic s9(7)v9(4) value 9999999.9999.
   05 filler pic s9(7)v9(4) value 12.
   05 filler pic s9(7)v9(4) value -7.
01 tbl redefines vals.
   05 v pic s9(7)v9(4) occurs 8.
procedure division.
    perform varying i from 1 by 1 until i > 8
        move v(i) to n
        display "value " n
        move n to e1 e2 e3 e4 e5 e6 e7 e8 e9 e10 e11 e12
        move n to e13 e14 e15 e16 e17 e18 e19 e20 e21 e22 e23
        display "[" e1 "][" e2 "][" e3 "][" e4 "][" e5 "][" e6 "]"
        display "[" e7 "][" e8 "][" e9 "][" e10 "][" e11 "][" e12 "]"
        display "[" e13 "][" e14 "][" e15 "][" e16 "][" e17 "][" e18 "]"
        display "[" e19 "][" e20 "][" e21 "][" e22 "][" e23 "]"
        compute e1 rounded = n * 3
        compute e3 = n / 7
        compute e7 rounded = n - 1
        display "c [" e1 "][" e3 "][" e7 "]"
    end-perform
    stop run.
