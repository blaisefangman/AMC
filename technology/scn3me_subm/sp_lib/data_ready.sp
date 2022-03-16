
.SUBCKT data_ready bl br sen dr vdd gnd
M0 sen_bar sen gnd gnd n w=2.4u l=0.6u
M1 sen_bar sen vdd vdd p w=2.4u l=0.6u
M2 dr sen_bar gnd gnd n w=2.4u l=0.6u
M3 n1 sen_bar vdd vdd p w=2.4u l=0.6u
M4 dr bl n1 vdd p w=2.4u l=0.6u
M5 dr br n1 vdd p w=2.4u l=0.6u
.ENDS data_ready
