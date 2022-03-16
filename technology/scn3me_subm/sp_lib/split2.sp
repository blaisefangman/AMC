
.SUBCKT split2 D Q bm_in bm_out en1_S en2_S reset S vdd gnd
M1 net_1 en2_S gnd gnd n w=2.1u l=0.6u
M2 net_2 bm_in net_1 gnd n w=2.1u l=0.6u
M3 net_3 en1_S net_2 gnd n w=2.1u l=0.6u
M4 net_4 S net_3 gnd n w=2.1u l=0.6u
M5 net_4 en1_S net_5 vdd p w=1.8u l=0.6u
M6 vdd en2_S net_5 vdd p w=1.8u l=0.6u
M7 Q net_4 vdd vdd p w=2.4u l=0.6u
M8 Q net_4 gnd gnd n w=1.2u l=0.6u
M9 reset_bar reset vdd vdd p w=2.4u l=0.6u
M10 reset_bar reset gnd gnd n w=1.2u l=0.6u
M11 net_4 reset_bar vdd vdd p w=1.8u l=0.6u
M12 net_4 Q q1 gnd n w=1.2u l=1.2u
M13 net_4 Q p1 vdd p w=2.4u l=1.2u
M14 q1 vdd gnd gnd n w=1.2u l=6u
M15 p1 gnd vdd vdd p w=2.4u l=6u
M16 net_6 en2_S gnd gnd n w=2.1u l=0.6u
M17 net_7 D net_6 gnd n w=2.1u l=0.6u
M18 net_8 en1_S net_7 gnd n w=2.1u l=0.6u
M19 net_9 S net_8 gnd n w=2.1u l=0.6u
M20 net_9 en1_S net_10 vdd p w=1.8u l=0.6u
M21 vdd en2_S net_10 vdd p w=1.8u l=0.6u
M22 net_9 reset_bar vdd vdd p w=1.8u l=0.6u
M23 bm_out net_9 vdd vdd p w=2.4u l=0.6u
M24 bm_out net_9 gnd gnd n w=1.2u l=0.6u
M25 net_9 bm_out q11 gnd n w=1.2u l=1.2u
M26 net_9 bm_out p11 vdd p w=2.4u l=1.2u
M27 q11 vdd gnd gnd n w=1.2u l=6u
M28 p11 gnd vdd vdd p w=2.4u l=6u
.ENDS split2

