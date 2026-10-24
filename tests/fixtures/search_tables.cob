identification division.
program-id. search-tables.
data division.
working-storage section.
01 tbl.
   05 ent occurs 8 ascending key k1 descending key k2 indexed by ix jx.
      10 k1 pic 99.
      10 k2 pic x.
      10 v pic x(3).
01 vals pic x(48) value "01ZAAA02YBBB02XCCC05ZDDD05YEEE07ZFFF09ZGGG09AHHH".
01 n pic 99.
01 cnt pic 9(4).
01 w usage index.
01 odo-n pic 9 value 4.
01 vt.
   05 ve pic x occurs 1 to 6 depending on odo-n indexed by vx.
procedure division.
    move vals to tbl
    move "abcdef" to vt
    set ix to 1
    search ent at end display "not found"
        when v(ix) = "DDD" display "found DDD at " ix
    end-search
    set ix to 1
    search ent varying n at end display "end n " n
        when k2(ix) = "Q" display "never"
    end-search
    set ix to 3
    search ent varying jx
        when k1(jx) = 9 display "jx " jx
    end-search
    search all ent at end display "all not found"
        when k1(ix) = 5 and k2(ix) = "Y" display "all found " ix " " v(ix)
    end-search
    search all ent at end display "all not found 2"
        when k1(ix) = 2 display "all 02 at " ix
    end-search
    search all ent at end display "all not found 3 " ix
        when k1(ix) = 4 display "never"
    end-search
    search all ent
        when k1(ix) = 9 and k2(ix) = "A" display "9A " v(ix)
    end-search
    set vx to 1
    search ve at end display "ve end " vx
        when ve(vx) = "e" display "never e"
    end-search
    set w to 2 set ix to 2
    search ent varying w when v(ix) = "FFF" display "w " w " ix " ix end-search
    stop run.
