identification division.
program-id. environment-case.
*> common.c : environnement, arguments et ligne de commande.
data division.
working-storage section.
01 v          pic x(10).
01 n          pic s9(4).
01 envname    pic x(12) value "C2R_X   ".
01 blank-var  pic x(4) value spaces.
01 argc       pic 99.
01 argc-text  pic x(10).
01 a          pic x(6).
01 cl-short   pic x(8).
01 cl-long    pic x(40).
01 i          pic 9.
procedure division.
    display "C2R_X" upon environment-name
    accept v from environment-value
        on exception display "absent [" v "] " function exception-status
                     end-display
        not on exception display "present"
    end-accept
    display "val 1  " upon environment-value
    accept v from environment-value
    display "[" v "]"
    move all "z" to v
    accept v from environment envname
        not on exception display "not first [" v "]" end-display
        on exception display "never"
    end-accept
    set environment "C2R_N" to "123"
    accept n from environment "C2R_N"
    display n
    accept n from environment "C2R_MISSING"
        on exception display "missing " n end-display
    end-accept
    set environment "C2R_E" to spaces
    set environment "C2R_F" to function upper-case ("low")
    accept v from environment "C2R_F"
    display "[" v "]"
    move "qq" to v
    accept v from environment "C2R_E"
    display "[" v "]"
    display "A=B" upon environment-name
    display "x" upon environment-value
        on exception display "setenv refused" end-display
    end-display
    display blank-var upon environment-name
    display "y" upon environment-value
        on exception display "no name" end-display
        not on exception display "named" end-display
    end-display
    call "SYSTEM" using "echo child:$C2R_X"
    accept argc from argument-number
    accept argc-text from argument-number
    display argc " [" argc-text "]"
    perform varying i from 1 by 1 until i > 5
        accept a from argument-value
            on exception display "end of arguments " i end-display
                         exit perform
        end-accept
        display i " [" a "]"
    end-perform
    display 2 upon argument-number
    accept a from argument-value
    display "again [" a "]"
    display 9 upon argument-number
        on exception display "no argument 9" end-display
    end-display
    display -1 upon argument-number
    accept a from argument-value
    display "absolute [" a "]"
    accept cl-short from command-line
    accept cl-long from command-line
    display "[" cl-short "] [" cl-long "]"
    display "replaced line" upon command-line
    accept cl-long from command-line
    display "[" cl-long "]"
    stop run.
