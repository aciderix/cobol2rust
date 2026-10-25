*> SORT of a table (cob_table_sort): glibc qsort, a stable merge sort; keys
*> by cob_numeric_cmp or memcmp, at their offset in their parent item
*> (cb_emit_sort_init: PAIR-DIGIT is read at offset 1 of the element, its
*> offset in PAIR-GROUP); the OCCURS KEY when the KEY phrase is absent, the
*> whole element for KEY without names; the active ODO count.
identification division.
program-id. table-sort.
data division.
working-storage section.
01 counties-text pic x(45) value
   "CORK 050AMAYO 010BKERRY050CDOWN 020DCLARE050E".
01 counties redefines counties-text.
   02 county occurs 5 ascending key county-pop.
      03 county-name pic x(5).
      03 county-pop pic 9(3).
      03 county-tag pic x.
01 i pic 9.
01 n pic 9 value 3.
01 odo-table.
   02 odo-entry pic x(2) occurs 1 to 5 depending on n.
01 pair-text pic x(15) value "xB2yA1zC3wA0vB1".
01 pairs.
   02 pair-entry occurs 5.
      03 pair-mark pic x.
      03 pair-group.
         04 pair-letter pic x.
         04 pair-digit pic 9.
procedure division.
    sort county on descending key county-pop county-name
    perform show
    sort county on ascending key county-name
    perform show
    sort county
    perform show
    sort county on descending key
    perform show
    move "EEDDCCBBAA" to odo-table
    sort odo-entry on ascending key odo-entry
    display "odo [" odo-table "]"
    move pair-text to pairs
    sort pair-entry on ascending key pair-digit
    display "pairs [" pairs "]"
    stop run.
show.
    perform varying i from 1 by 1 until i > 5
        display county-name (i) county-pop (i) county-tag (i) with no advancing
    end-perform
    display " ".
