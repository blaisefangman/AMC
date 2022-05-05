

.SUBCKT merge D Q en1_M en2_M reset M vdd gnd
M1 net_1 en1_M gnd gnd n w=2.1u l=0.6u 
M2 net_2 D net_1 gnd n w=2.1u l=0.6u  
M3 net_3 en2_M net_2 gnd n w=2.1u l=0.6u  
M4 Q1 M net_3 gnd n w=2.1u l=0.6u  
M5 Q1 en2_M net_5 vdd p w=1.8u l=0.6u
M6 vdd en1_M net_5 vdd p w=1.8u l=0.6u    
M7 reset_bar reset vdd vdd p w=2.4u l=0.6u
M8 reset_bar reset gnd gnd n w=1.2u l=0.6u
M9 Q1 reset_bar vdd vdd p w=1.8u l=0.6u
M10 M_bar M vdd vdd p w=2.4u l=0.6u
M11 M_bar M gnd gnd n w=1.2u l=0.6u
M12 Q M_bar pre_Q vdd p w=2.4u l=0.6u
M13 Q M pre_Q gnd n w=1.2u l=0.6u
M14 pre_Q Q1 vdd vdd p m=1 w=2.4u l=0.6u
M15 pre_Q Q1 gnd gnd n m=1 w=1.2u l=0.6u
.ENDS merge

