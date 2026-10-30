identification division.
program-id. pointers.
environment division.
input-output section.
file-control.
    select dyn-file assign using dyn-name
        organization line sequential file status dyn-fs.
data division.
file section.
fd dyn-file.
01 dyn-rec pic x(4).
working-storage section.
01 p usage pointer.
01 q usage is pointer value null.
01 g.
    02 gp pointer.
    02 gx pic x(4) value "ABCD".
01 h.
    02 hp usage pointer.
    02 hx pic x(4).
01 x pic x(8) value "12345678".
01 n pic 9 value 3.
01 dyn-fs pic xx.
01 b based.
    02 b1 pic x(3) value "B1V".
    02 b2 pic 99 value 42.
    02 filler pic x value "F".
    02 b3 pic x(2).
    02 b4 usage pointer.
01 c pic x(5) based value "CVALU".
01 dyn-name pic x(8) based.
linkage section.
01 y pic x(4).
01 z pic x(2).
procedure division.
    display "len " function length(p) " " length of g.
    if p = null display "p null" else display "p not null" end-if.
    if q = nulls display "q nulls" end-if.
    display "d [" q "] [" g "]".
    set p to address of x.
    if p = address of x display "eq addr" end-if.
    set q to p.
    if q = p display "q=p" end-if.
    set p up by 2.
    set address of y to p.
    display "y " y.
    set p down by 1.
    set address of y to p.
    display "y " y.
    set q up by n.
    set address of y to q.
    display "y " y.
    if p < q display "p before q" end-if.
    move g to h.
    if hp = null display "hp null " hx end-if.
    set gp to address of x.
    move g to h.
    set address of y to hp.
    display "via group " y.
    set address of z to address of y.
    set address of z up by 1.
    display "z " z.
    move "zz" to z.
    display "x " x.
    set address of y to null.
    if address of y = null display "y null" end-if.
    move p to q.
    if q = p display "move ok" end-if.
    allocate 6 characters initialized to "AB" returning p.
    set address of y to p.
    display "a1 [" y "]".
    free p.
    if p = null display "freed null" end-if.
    allocate n characters initialized to all "xy" returning p.
    set address of z to p.
    display "a2 [" z "]".
    allocate 6 characters initialized returning q.
    set address of y to q.
    if y = low-values display "a3 low" end-if.
    allocate b initialized.
    display "a4 [" b(1:8) "]".
    if b4 = null display "b4 null" end-if.
    allocate c initialized returning q.
    display "a5 [" c "]".
    set address of y to q.
    display "a6 [" y "]".
    free c.
    if address of c = null display "c freed" end-if.
    free q.
    if q not = null display "q held" end-if.
    set p to address of x.
    free p.
    if p not = null display "ws not freed" end-if.
    allocate 0 characters returning q.
    if q = null display "zero alloc null" end-if.
    open input dyn-file.
    display "open without name " dyn-fs.
    allocate dyn-name.
    move "NONE.TXT" to dyn-name.
    open input dyn-file.
    display "open none " dyn-fs.
    free dyn-name.
    call "keeper" using x.
    call "keeper" using x.
    cancel "keeper".
    call "keeper" using x.
    stop run.
end program pointers.

identification division.
program-id. keeper.
data division.
working-storage section.
01 calls pic 9 value 0.
01 held pic x(6) based.
linkage section.
01 arg pic x(8).
01 view-of pic x(2).
procedure division using arg.
    add 1 to calls.
    if address of view-of = null
        display "keeper " calls " view-of null"
        set address of view-of to address of arg
    else
        display "keeper " calls " view-of " view-of
    end-if.
    if address of held = null
        display "keeper " calls " held null"
        allocate held initialized
        move "HELD" to held
    else
        display "keeper " calls " held " held
    end-if.
    goback.
end program keeper.
