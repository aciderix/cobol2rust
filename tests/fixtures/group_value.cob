*> Group VALUE fills the group as alphanumeric data; group USAGE applies to leaves.
identification division. program-id. group-value.
data division. working-storage section.
01 ga value "40537". 02 i occurs 5 pic 9.
01 gb value "AB". 02 a pic x(3). 02 b pic 9(2).
01 gc value spaces. 02 n pic 9(3).
01 gd value zero. 02 a pic x(3).
01 ge. 02 h value "XY". 03 a pic x. 03 b pic x. 02 c pic x value "Z".
01 gh value "12". 02 n pic 9(4) comp.
01 gj usage comp. 02 a pic s9(4). 02 b pic 9(9).
01 gk comp-3. 02 a pic s9(3). 02 h. 03 b pic 9(4).
01 gt. 02 e occurs 3 value "AB". 03 a pic x. 03 b pic x.
01 gz value zeros. 02 n pic 9(2). 02 x pic x(2).
procedure division.
    display "[" ga "][" gb "][" gc "][" gd "][" ge "][" gh "][" gt "][" gz "]"
    display i(2)
    move -12 to a of gj move 123456789 to b of gj move -5 to a of gk move 42 to b of gk
    display "[" gj "][" gk "]" a of gj " " a of gk " " b of gk
    initialize ga gb display "[" ga "][" gb "]"
    stop run.
