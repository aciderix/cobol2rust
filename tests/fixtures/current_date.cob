identification division.
program-id. current-date-case.
data division.
working-storage section.
01 compiled pic x(21).
01 now-text pic x(21).
01 parts redefines now-text.
   02 year pic 9(4).
   02 month pic 99.
   02 day-of pic 99.
   02 clock pic 9(8).
   02 zone pic x(5).
procedure division.
    move function current-date to now-text.
    move function when-compiled to compiled.
    if year > 2000 and month >= 1 and month <= 12 and day-of >= 1 and day-of <= 31
        and clock is numeric and zone = "+0000"
        display "current-date ok"
    end-if.
    if compiled <= now-text and compiled(17:5) = "+0000"
        display "when-compiled ok"
    end-if.
    stop run.
