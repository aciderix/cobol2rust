*> cob_chk_file_mapping: each name read from stdin is opened, written and
*> closed; the environment maps it (DD_name, dd_name, name, $VAR, COB_FILE_PATH).
identification division.
program-id. assign-mapping.
environment division.
input-output section.
file-control.
    select out-file assign to ws-name file status is ws-status.
data division.
file section.
fd out-file.
01 out-record pic x(40).
working-storage section.
01 ws-name pic x(60).
01 ws-status pic xx.
procedure division.
    perform with test after until ws-name = "end"
        move spaces to ws-name
        accept ws-name
        if ws-name not = "end"
            open output out-file
            display ws-status " " ws-name
            if ws-status = "00"
                move ws-name to out-record
                write out-record
                close out-file
            end-if
        end-if
    end-perform
    stop run.
