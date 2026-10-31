       identification division.
       program-id. open-several.
       environment division.
       input-output section.
       file-control.
           select a assign "open-several-missing.dat" organization line sequential
               status fa.
           select b assign "open-several-out.dat" organization line sequential
               status fb.
           select c assign "open-several-missing2.dat" organization line sequential.
       data division.
       file section.
       fd a.
       01 ra pic x.
       fd b.
       01 rb pic x.
       fd c.
       01 rc pic x.
       working-storage section.
       01 fa pic xx.
       01 fb pic xx.
       procedure division.
       declaratives.
       da section.
           use after error procedure on a.
       da1.
           display "use a " fa.
       dc section.
           use after error procedure on c.
       dc1.
           display "use c".
       end declaratives.
       main section.
       m1.
           open input a, output b, input c
           display "after 1 " fa " " fb
           close b c a
           open input c, output b
           display "after 2"
           close b c a
           open output b, input c
           display "after 3"
           stop run.
