identification division.
program-id. copy-replacing.
data division.
working-storage section.
01 first-rec. copy "replacing_items.cpy".
01 second-rec. copy "replacing_items.cpy"
       replacing item-a by other-a
                 ==PIC 9(2) VALUE 12== by ==PIC 9(3) VALUE 345==
                 "C, D" by "Q".
01 target pic x(3).
01 counter pic 9(3) value 0.
procedure division.
    display first-rec "|" second-rec
    copy "replacing_code.cpy" replacing ==1== by ==10== target by target
         =="TEXT"== by =="NEW"==.
    copy "replacing_code.cpy" replacing ==ITEM-A== by ==other-a==.
    stop run.
