
.SUBCKT write_driver din bm bl br en pchg vdd gnd
M1 din_bar din gnd gnd n w=1.2u l=0.6u
M2 din_bar din vdd vdd p w=2.1u l=0.6u
M3 en_bar bm net_5 gnd n w=1.2u l=0.6u 
M4 net_5 en gnd gnd n w=1.2u l=0.6u
M5 en_bar bm vdd vdd p w=2.1u l=0.6u 
M6 en_bar en vdd vdd p w=2.1u l=0.6u
M7 en1 en_bar gnd gnd n w=1.2u l=0.6u 
M8 en1 en_bar vdd vdd p w=2.1u l=0.6u 
M9 vdd din net_1 vdd p w=7.8u l=0.6u 
M10 net_1 en_bar br vdd p w=7.8u l=0.6u  
M11 br en1 net_2 gnd n w=3.9u l=0.6u 
M12 net_2 din gnd gnd n w=3.9u l=0.6u 
M13 vdd din_bar net_3 vdd p w=7.8u l=0.6u
M14 net_3 en_bar bl vdd p w=7.8u l=0.6u  
M15 bl en1 net_4 gnd n w=3.9u l=0.6u
M16 net_4 din_bar gnd gnd n w=3.9u l=0.6u 
M17 bl pchg vdd vdd p w=2.1u l=0.6u
M18 br pchg vdd vdd p w=2.1u l=0.6u 
.ENDS	write_driver

