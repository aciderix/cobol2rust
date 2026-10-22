>>SOURCE FORMAT FIXED
000100 identification division.
000200 program-id. fixed-continuation.
000300 environment division.
000400 configuration section.
000500 source-computer. GNU-Linux.
000600 object-computer. GNU-Linux.
000700 data division.
000800 working-storage section.
000900 01 n pic 9(4) value 12
001000-    34.
001100 procedure division.
001200     DISPL *> quote " inside comment
001300* A comment does not interrupt the continued word.
001400-AY n "AB"
001500-    "CD"
001600     stop run.
