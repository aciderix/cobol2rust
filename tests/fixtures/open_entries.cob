       identification division.
       program-id. open-entries.
       environment division.
       input-output section.
       file-control.
           select a assign "open-entries-missing.dat" organization line sequential.
           select b assign "open-entries-out.dat" organization line sequential.
           select c assign "open-entries-out2.dat" organization line sequential.
       data division.
       file section.
       fd a.
       01 ra pic x.
       fd b.
       01 rb pic x.
       fd c.
       01 rc pic x.
       procedure division.
           open output b input a c
           stop run.
