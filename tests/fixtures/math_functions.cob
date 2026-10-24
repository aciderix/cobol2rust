identification division.
program-id. math-functions.
*> SQRT, LOG, LOG10, EXP, trigonometric functions, PI, E and
*> STANDARD-DEVIATION: libcob computes them with 2048-bit GMP floats and
*> keeps 96 significant digits, rounded (mpf_get_str).
data division.
working-storage section.
01 r pic s9(3)v9(15).
01 big pic s9(18).
01 tiny pic sv9(18).
procedure division.
    compute r = function sqrt(2). display r.
    compute r = function sqrt(0.0002). display r.
    compute r = function log(2). display r.
    compute r = function sin(1). display r.
    compute r = function atan(1). display r.
    compute r = function exp(1). display r.
    compute r = function log10(3). display r.
    compute r = function cos(0.5). display r.
    compute r = function tan(0.5). display r.
    compute r = function asin(0.5). display r.
    compute r = function acos(0.5). display r.
    compute r = function acos(-1). display r.
    compute r = function asin(1). display r.
    compute r = function sqrt(16). display r.
    compute r = function log(0.5). display r.
    compute r = function sin(-100.25). display r.
    compute r = function cos(12345.6789). display r.
    compute r = function atan(-250.5). display r.
    compute r = function exp(-3.5). display r.
    compute big = function exp(50). display big.
    compute r = function pi. display r.
    compute r = function e. display r.
    compute r = function standard-deviation(1 2 3 4 10). display r.
    compute tiny = function sin(0.00000000000000000001). display tiny.
    compute r = function log10(123456.789) * 2 + 1. display r.
    compute r rounded = function sqrt(3). display r.
    stop run.
