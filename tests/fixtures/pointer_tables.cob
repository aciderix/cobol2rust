       identification division.
       program-id. pointer-tables.
       data division.
       working-storage section.
       01 t.
          02 tp usage pointer occurs 3.
       01 g.
          02 gp usage pointer.
          02 gn pic 99 value 7.
          02 gx pic x(2) value "ab".
       01 x pic x(6) value "ABCDEF".
       01 i pic 9 value 2.
       01 bb based.
          02 bb1 pic x(2).
          02 bb2 pic x(2).
       01 br redefines bb pic x(4).
       linkage section.
       01 y pic x(3).
       procedure division.
           set tp(i) to address of x(3:2).
           set address of y to tp(2).
           display "y " y.
           if tp(1) = null and tp(3) = null display "others null".
           set gp to address of x.
           initialize g.
           if gp = null display "init null " gn " [" gx "]".
           set gp to address of x.
           initialize g replacing numeric by 5 alphanumeric by "zz".
           if gp = null display "repl null " gn " [" gx "]"
           else display "repl kept " gn " [" gx "]".
           allocate bb initialized.
           move "WXYZ" to br.
           display "bb " bb1 " " bb2.
           set address of y to address of bb2.
           display "y2 " y(1:2).
           stop run.
