identification division.
program-id. sections.
procedure division.
    perform alpha-section
    display "BACK"
    perform first-paragraph through beta-section
    perform empty-section
    stop run.
alpha-section section.
    display "ALPHA".
first-paragraph.
    display "FIRST"
    exit paragraph
    display "UNREACHABLE".
second-paragraph.
    exit
    display "SECOND".
empty-section section.
beta-section section.
    display "BETA".
last-paragraph.
    display "END".
