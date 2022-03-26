######################################################################
#
#Copyright (c) 2018-2021 Samira Ataei
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA. (See LICENSE for licensing information)
#
######################################################################


""" This file generates simple spice cards for simulation.  There are
various functions that can be be used to generate stimulus for other
simulations as well. """

import tech
import debug
import subprocess
import os, sys, shutil
from os import path
import charutils 
import numpy as np
from globals import OPTS, get_tool
import time
import design
import math
import trim_spice


class functional_test():
    """ Class for providing stimuli and decks for functional verification """

    def __init__(self, size, corner, name, w_per_row, num_rows, mask, power_gate, load=tech.spice["input_cap"], slew=tech.spice["rise_time"]):
        self.vdd_name = tech.spice["vdd_name"]
        self.gnd_name = tech.spice["gnd_name"]
        self.voltage = tech.spice["nom_supply_voltage"]
        self.name = name
        self.w_per_row = w_per_row
        self.num_rows = num_rows
        self.mask = mask
        self.power_gate = power_gate

        self.deck_file = "test.sp"
        self.test = open(OPTS.AMC_temp+"test.v", "w")
        self.dut = open(OPTS.AMC_temp+"dut.sp", "w")
        self.deck = open(OPTS.AMC_temp+"test.sp", "w")
        self.source = open(OPTS.AMC_temp+"source.v", "w")
        self.cosim = open(OPTS.AMC_temp+"setup.init", "w")
        self.make = open(OPTS.AMC_temp+"Makefile", "w")
        
        (self.addr_bit, self.data_bit) = size
        (self.process, self.voltage, self.temperature) = corner
        self.device_models = tech.SPICE_MODEL_DIR
        
        self.run_sim(load, slew)
    
    def inst_sram(self, abits, dbits, suffix, sram_name):
        """ Function to instatiate an SRAM subckt. """
        
        self.dut.write("X{0} ".format(sram_name))
        for i in range(dbits):
            self.dut.write("DIN{0}{1} ".format(i, suffix))
        for i in range(dbits):
            self.dut.write("DOUT{0}{1} ".format(i,suffix))
        for i in range(abits):
            self.dut.write("ADDR{0}{1} ".format(i, suffix))
        if self.mask:
            for i in range(dbits):
                self.dut.write("BM{0}{1} ".format(i, suffix))
        self.dut.write("reset ")
        for i in ["r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"]:
            self.dut.write("{0}{1} ".format(i, suffix))
        if self.power_gate:
            self.dut.write("sleep ")
        self.dut.write("{0} {1} ".format(self.vdd_name, self.gnd_name))
        self.dut.write("{0}\n".format(sram_name))


    def dut_generator(self, abits, dbits, load, sram_name, w_per_row, num_rows):
        """ Function to write DUT netlist. """
        
        self.pmos_name = tech.spice["pmos"]
        self.nmos_name = tech.spice["nmos"]
        self.minwidth_tx = tech.drc["minwidth_tx"]
        self.minlength_tx = tech.drc["minlength_channel"]
        spice_name=sram_name

        self.dut.write("\n ")
        #Don't trim the netlist for power calculations
        #if OPTS.trim_netlist:
            #filename="{0}{1}".format(OPTS.AMC_temp, "{0}.sp".format(sram_name))
            #reduced_file="{0}{1}".format(OPTS.AMC_temp, "reduced.sp")
            #trim_spice.trim_spice(filename, reduced_file, dbits, w_per_row, num_rows, "1"*abits, "0"*abits)
            #spice_name="reduced"
        
        self.dut.write(".inc {0}.sp\n\n".format(spice_name))
        #self.dut.write("V{0} {0} 0 dc {1}v\n".format("test"+self.vdd_name, self.voltage))
        #self.dut.write("V{0} {0} 0 dc 0.0v\n".format("test"+self.gnd_name))
        self.dut.write("\n")
        self.dut.write(".subckt DUT ")
        for i in range(dbits):
            self.dut.write("DIN{0} ".format(i))
        for i in range(dbits):
            self.dut.write("DOUT{0} ".format(i))
        for i in range(abits):
            self.dut.write("ADDR{0} ".format(i))
        if self.mask:
            for i in range(dbits):
                self.dut.write("BM{0} ".format(i))
        
        for i in ["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"]:
            self.dut.write("{0} ".format(i))
        if self.power_gate:
            self.dut.write("sleep ")

        self.dut.write("{0} {1} ".format(self.vdd_name, self.gnd_name))
        self.dut.write("\n")
        self.inst_sram(abits, dbits, "", sram_name)
        self.dut.write(".ends\n")

        self.dut.write("\n")
        self.create_buffer()

        self.dut.write(".subckt wrapper ")
        for i in range(dbits):
            self.dut.write("DIN{0} ".format(i))
        for i in range(dbits):
            self.dut.write("DOUT{0} ".format(i))
        for i in range(abits):
            self.dut.write("ADDR{0} ".format(i))
        if self.mask:
            for i in range(dbits):
                 self.dut.write("BM{0} ".format(i))

        for i in ["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"]:
            self.dut.write("{0} ".format(i))
        if self.power_gate:
            self.dut.write("sleep ")
        self.dut.write("\n")
        
        self.inst_sram(abits, dbits, "_buf", "DUT")
        self.dut.write("\n")
        
        din_list=[]
        for i in range(dbits):
            din_list.append("DIN{0}".format(i))
        addr_list=[]
        for i in range(abits):
            addr_list.append("ADDR{0}".format(i))
        dout_list=[]
        for i in range(dbits):
            dout_list.append("DOUT{0}".format(i))

        ctrl_list1 =["r", "w", "rw", "rreq", "wreq"]
        ctrl_list2 =["ack", "wack", "rack"]
        self.add_in_buffer(din_list)
        self.dut.write("\n")
        self.add_in_buffer(addr_list)
        self.dut.write("\n")
        self.add_in_buffer(ctrl_list1)
        self.dut.write("\n")
        self.add_out_buffer(dout_list)
        self.dut.write("\n")
        self.add_out_buffer(ctrl_list2)
        self.dut.write("\n")
        if self.mask:
            bm_list=[]
            for i in range(dbits):
                bm_list.append("BM{0}".format(i))
            self.add_in_buffer(bm_list)
            self.dut.write("\n")

        self.add_cap_load(dout_list, load)
        ctrl_list2 =["ack", "rack", "wack"]
        self.dut.write("\n")
        self.add_cap_load(ctrl_list2, load)
        self.dut.write("\n")
        self.dut.write(".ends\n")

        self.dut.close()

    def spice_deck(self, slew, load):
        """ Function to write the Finesim spice deck. """
        
        self.deck.write("* SPICE DECK for slew = {0} and load = {1}\n\n".format(slew, load))
        self.deck.write(".global {0} {1}\n".format(self.vdd_name, self.gnd_name))
        self.deck.write("vpwr0 {0} 0 dc {1}v\n".format(self.vdd_name, self.voltage))
        self.deck.write("vpwr1 {0} 0 dc {1}v\n\n".format(self.gnd_name, 0))
        if tech.info["name"]=="tsmc65nm":
            self.deck.write(".lib {0} {1}\n".format(self.device_models, self.process))
            
        else:
            self.deck.write(".include {0}\n".format(self.device_models))
        self.deck.write(".inc dut.sp\n\n")
        self.deck.write(".option finesim_measout=2\n")
        self.deck.write(".option finesim_mode=spicemd\n")
        self.deck.write(".print in(V(vdd))\n")
        self.deck.write(".print in(V(gnd))\n\n")
        if self.power_gate:
            self.deck.write(".print in(xdut.xdut.xsram.vvdd)\n\n")
        
        self.gen_meas_delay("write_delay", "TOP.DUT.w", "TOP.DUT.w", 
                           (0.5*self.voltage), (0.5*self.voltage), 
                           "RISE", "RISE", 3, 4, "1n")
        self.gen_meas_delay("read_delay", "TOP.DUT.r", "TOP.DUT.r", 
                           (0.5*self.voltage), (0.5*self.voltage), 
                           "RISE", "RISE", 2, 3, "1n")
        self.gen_meas_delay("read_write_delay", "TOP.DUT.rw", "TOP.DUT.rw", 
                           (0.5*self.voltage), (0.5*self.voltage), 
                           "RISE", "RISE", 2, 3, "1n")
        
        self.gen_meas_delay("slew_hl", "TOP.DUT.r", "TOP.DUT.r", 
                           (0.9*self.voltage), (0.1*self.voltage), 
                           "FALL", "FALL", 1, 1, "0.001n")
        self.gen_meas_delay("slew_lh", "TOP.DUT.r", "TOP.DUT.r", 
                           (0.1*self.voltage), (0.9*self.voltage), 
                           "RISE", "RISE", 1, 1, "0.001n")

        self.gen_meas_delay("w_intvl", "TOP.DUT.w", "TOP.DUT.w", 
                           (0.5*self.voltage), (0.5*self.voltage), 
                           "RISE", "FALL", 1, 4, "0.001n")
        self.gen_meas_delay("r_intvl", "TOP.DUT.r", "TOP.DUT.r", 
                           (0.5*self.voltage), (0.5*self.voltage), 
                           "RISE", "FALL", 1, 3, "0.001n")
        self.gen_meas_delay("rw_intvl", "TOP.DUT.rw", "TOP.DUT.rw", 
                           (0.5*self.voltage), (0.5*self.voltage), 
                           "RISE", "FALL", 1, 3, "0.001n")

        self.gen_meas_power("leakage_power", "1n", "4n")
        
        self.gen_meas_current("write_current", "5n", "w_intvl+5n")
        self.gen_meas_current("read_current", "w_intvl+5n", "w_intvl+r_intvl+5n")
        self.gen_meas_current("read_write_current", "w_intvl+r_intvl+5n", "w_intvl+r_intvl+rw_intvl+5n")
        
        self.deck.write(".measure write_power param=V(vdd)*write_current\n")
        self.deck.write(".measure read_power param=V(vdd)*read_current\n")
        self.deck.write(".measure read_write_power param=V(vdd)*read_write_current\n")
        
        self.deck.write(".end\n")
        self.deck.close()
        

    def gen_meas_delay(self, meas_name, trig_name, targ_name, trig_val, targ_val, trig_dir, targ_dir, trig_num, targ_num, trig_td):
        """ Creates the .measure statement for the measurement of delay, setup and hold"""
        
        measure_string=".measure tran {0} TRIG V({1}) VAL={2} {3}={4} TD={5} TARG V({6}) VAL={7} {8}={9}\n"
        self.deck.write(measure_string.format(meas_name, trig_name, trig_val, trig_dir, trig_num, trig_td,
                                              targ_name, targ_val, targ_dir, targ_num))
    
    def gen_meas_power(self, meas_name, start, stop):
        """ Creates the .measure statement for the measurement of power """
        
        power_exp = "par('-1*(V(vdd)*I(vpwr0))')"
        measure_string=".measure tran {0} AVG {1} from={2} to={3}\n"
        self.deck.write(measure_string.format(meas_name, power_exp, start, stop))

    def gen_meas_current(self, meas_name, start, stop):
        """ Creates the .measure statement for the measurement of current """
        
        measure_string=".measure tran {0} AVG I(vpwr0) from={1} to={2}\n"
        self.deck.write(measure_string.format(meas_name, start, stop))
    
    def verilog_testbench(self,abits, dbits):
        """ Function to write the Verilog Testbench. """
        
        self.test.write("`timescale 1ns / 10ps;\n")
        self.test.write("`include \"source.v\"\n")
        self.test.write("`define WORD_SIZE {0};\n".format(dbits))
        self.test.write("`define ADDR_SIZE {0};\n\n".format(abits))
        self.test.write("module wrapper( ")
        for i in range(dbits):
            self.test.write("DIN{0}, ".format(i))
        for i in range(dbits):
            self.test.write("DOUT{0}, ".format(i))
        for i in range(abits):
            self.test.write("ADDR{0}, ".format(i))
        if self.mask:
            for i in range(dbits):
                self.test.write("BM{0}, ".format(i))
        
        for i in ["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq"]:
            self.test.write("{0}, ".format(i))
        
        if self.power_gate:
            self.test.write("wack, sleep);\n")
        else:
            self.test.write("wack);\n")
        for i in range(dbits):
            self.test.write("    input DIN{0};\n".format(i))
        for i in range(dbits):
            self.test.write("    output DOUT{0};\n".format(i))
        for i in range(abits):
            self.test.write("    input ADDR{0};\n".format(i))
        if self.mask:
            for i in range(dbits):
                self.test.write("    input BM{0};\n".format(i))
        
        for i in ["reset", "r", "w", "rw", "rreq", "wreq"]:
            self.test.write("    input {0};\n".format(i))
        if self.power_gate:
            self.test.write("    input sleep;\n")
        
        for i in ["ack", "rack", "wack"]:
            self.test.write("    output {0};\n".format(i))
        #self.test.write("    initial $nsda_module();\n")
        self.test.write("endmodule\n\n")

        self.test.write("module top;\n")
        self.test.write("    parameter WORD_SIZE = `WORD_SIZE;\n")
        self.test.write("    parameter ADDR_SIZE = `ADDR_SIZE;\n")
        for i in range(dbits):
            self.test.write("    wire DIN{0};\n".format(i))
        for i in range(dbits):
            self.test.write("    wire DOUT{0};\n".format(i))
        for i in range(abits):
            self.test.write("    wire ADDR{0};\n".format(i))
        if self.mask:
            for i in range(dbits):
                self.test.write("    wire BM{0};\n".format(i))
        
        for i in ["r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"]:
            self.test.write("    wire {0};\n".format(i))
        self.test.write("    wire [WORD_SIZE-1:0] Data_In;\n")
        self.test.write("    wire [ADDR_SIZE-1:0] Addr_In;\n")
        if self.mask:
            self.test.write("    wire [WORD_SIZE-1:0] Bm_In;\n")
        
        
        for i in ["r_In", "w_In", "rw_In", "rreq_In", "wreq_In"]:
            self.test.write("    wire {0};\n".format(i))
        for i in ["reset", "{0}".format(self.vdd_name), "{0}".format(self.gnd_name)]:
            self.test.write("    reg {0};\n".format(i))
        if self.power_gate:
            self.test.write("    reg sleep;\n")
        
        self.test.write("    initial begin\n")
        self.test.write("        $timeformat(-12, 0, \"psec\", 10);\n")
        self.test.write("        {0} = 1;\n".format(self.vdd_name))
        self.test.write("        {0} = 0;\n".format(self.gnd_name))
        self.test.write("        reset = 1;\n")
        if self.power_gate:
            self.test.write("        sleep = 0;\n")
        self.test.write("        #5 reset = 0;\n")
        if self.power_gate:
            self.test.write("        #8 sleep = 1;\n")
        self.test.write("        #100 $finish;\n")
        self.test.write("    end\n")
        
        self.test.write("    source inputs(.Reset(reset), .DATA(Data_In), .ADDR(Addr_In), ")
        if self.power_gate:
            self.test.write(".Sleep(sleep),")
        if self.mask:
            self.test.write(".DATA(Data_In), .ADDR(Addr_In), .BM(Bm_In),")
        else:
            self.test.write(".DATA(Data_In), .ADDR(Addr_In), ")
        
        self.test.write(".R(r_In), .W(w_In), .RW(rw_In), .RREQ(rreq_In), .WREQ(wreq_In), ")
        self.test.write(".RACK(rack), .ACK(ack));\n\n")
        
        self.test.write("    assign{ ")
        for i in range(dbits-1):
            self.test.write("DIN{0}, ".format(i))
        self.test.write("DIN{0}".format(dbits))
        self.test.write("} = Data_In;\n\n")
        self.test.write("    assign{ ")
        for i in range(abits-1):
            self.test.write("ADDR{0}, ".format(i))
        self.test.write("ADDR{0}".format(abits-1))
        self.test.write("} = Addr_In;\n\n")
        if self.mask:
            self.test.write("    assign{ ")
            for i in range(dbits-1):
                self.test.write("BM{0}, ".format(i))
            self.test.write("BM{0}".format(dbits))
            self.test.write("} = Bm_In;\n\n")
        self.test.write("    assign{ ")
        for i in ["r", "w", "rw", "rreq"]:
            self.test.write("{0}, ".format(i))
        self.test.write("wreq} = {r_In, w_In, rw_In, rreq_In, wreq_In};\n\n")
        self.test.write("    wrapper dut(")
        for i in range(dbits):
            self.test.write("DIN{0}, ".format(i))
        for i in range(dbits):
            self.test.write("DOUT{0}, ".format(i))
        for i in range(abits):
            self.test.write("ADDR{0}, ".format(i))
        if self.mask:
            for i in range(dbits):
                self.test.write("BM{0}, ".format(i))
        for i in ["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq"]:
            self.test.write("{0}, ".format(i))
        if self.power_gate:
            self.test.write("wack, sleep);\n\n")
        else:
            self.test.write("wack);\n\n")
        port_list = ["reset", "r", "w", "rw", "ack", "rreq", "rack", "wreq", "wack"]
        if self.power_gate:
            port_list.append("sleep")
        for i in port_list:
            self.test.write("    always @(posedge {0}) begin \n".format(i))
            self.test.write("        $display(\"     %t {0} : 1\", $time);\n".format(i))
            self.test.write("    end\n")
            self.test.write("    always @(negedge {0}) begin \n".format(i))
            self.test.write("        $display(\"     %t {0} : 0\", $time);\n".format(i))
            self.test.write("    end\n")
        self.test.write("endmodule")
        self.test.close()

    def source_generator(self,abits, dbits, delay, slew):
        """ Function to write the Verilog input vectors. """
        
        self.source.write("`define WORD_SIZE {0};\n".format(dbits))
        self.source.write("`define ADDR_SIZE {0};\n\n".format(abits))
        self.source.write("module source(Reset, ") 
        if self.power_gate:
            self.source.write("Sleep, ") 
        if self.mask:
            self.source.write("DATA, BM, ADDR, R, W, RW, RREQ, WREQ, RACK, ACK);\n")
        else:
            self.source.write("DATA, ADDR, R, W, RW, RREQ, WREQ, RACK, ACK);\n")
        self.source.write("    parameter WORD_SIZE = `WORD_SIZE;\n")
        self.source.write("    parameter ADDR_SIZE = `ADDR_SIZE;\n")
        self.source.write("    input Reset;\n")
        if self.power_gate:
            self.source.write("    input Sleep;\n")
        
        self.source.write("    input ACK;\n")
        self.source.write("    input RACK;\n")
        self.source.write("    output [WORD_SIZE-1:0]DATA;\n")
        if self.mask:
            self.source.write("    output [WORD_SIZE-1:0]BM;\n")
        
        self.source.write("    output [ADDR_SIZE-1:0]ADDR;\n")
        self.source.write("    output R;\n")
        self.source.write("    output W;\n")
        self.source.write("    output RW;\n")
        self.source.write("    output RREQ;\n")
        self.source.write("    output WREQ;\n\n")
        self.source.write("    reg [WORD_SIZE-1:0]DATA;\n")
        if self.mask:
            self.source.write("    reg [WORD_SIZE-1:0]BM;\n")
        
        self.source.write("    reg [ADDR_SIZE-1:0]ADDR;\n")
        self.source.write("    reg R, W, RW, RREQ, WREQ;\n")
        self.source.write("    integer i, j, k;\n\n")
        self.source.write("    initial begin\n")
        self.source.write("        $display(\"Initializing....\", $time);\n")
        self.source.write("        DATA <= #{0} {1}'b{2};\n".format(delay, dbits, "0"*dbits))
        if self.mask:
            self.source.write("        BM <= #{0} {1}'b{2};\n".format(delay, dbits, "1"*dbits))
        
        self.source.write("        ADDR <= #{0} {1}'b{2};\n".format(delay, abits, "0"*abits))
        self.source.write("        R <= #{0} 0;\n".format(delay))
        self.source.write("        W <= #{0} 0;\n".format(delay))
        self.source.write("        RW <= #{0} 0;\n".format(delay))
        self.source.write("        RREQ <= #{0} 0;\n".format(delay))
        self.source.write("        WREQ <= #{0} 0;\n".format(delay))
        self.source.write("    end\n\n")
        
        if self.power_gate:
            self.source.write("    always @(posedge Sleep) begin\n")
            self.source.write("        $display(\"posedge of Sleep. Power is disconnected!\", $time);\n")
            self.source.write("        W <= #{0} 1'b0;\n".format(delay))
            self.source.write("        WREQ <= #{0} 1'b0;\n".format(delay))
            self.source.write("        RW <= #{0} 1'b0;\n".format(delay))
            self.source.write("        RREQ <= #{0} 1'b0;\n".format(delay))
            self.source.write("        R <= #{0} 1'b0;\n".format(delay))
            self.source.write("    end\n\n")
        
        
        self.source.write("    always @(negedge Reset) begin\n")
        self.source.write("        $display(\"Negedge of Reset. Test begins....\", $time);\n")
        self.source.write("        W <= #{0} 1'b1;\n".format(delay))
        self.source.write("        WREQ <= #{0} 1'b1;\n".format(delay))
        self.source.write("        i <= 0;\n")
        self.source.write("        j <= 0;\n")
        self.source.write("        k <= 0;\n")
        self.source.write("    end\n\n")
        self.source.write("    always @(posedge ACK) begin\n")
        self.source.write("        R <= #{0} 0;\n".format(delay))
        self.source.write("        W <= #{0} 0;\n".format(delay))
        self.source.write("        RW <= #{0} 0;\n".format(delay))
        self.source.write("        RREQ <= #{0} 0;\n".format(delay))
        self.source.write("        WREQ <= #{0} 0;\n".format(delay))
        self.source.write("        if (i < 4) begin\n")
        self.source.write("            i = i+1;\n")
        self.source.write("        end\n")
        self.source.write("        if (i == 4 & j != 4) begin\n")
        self.source.write("            j = j+1;\n")
        self.source.write("        end\n")
        self.source.write("        if (i == 4 & j== 4) begin\n")
        self.source.write("            k = k+1;\n")
        self.source.write("        end\n")
        self.source.write("    end\n\n")
        self.source.write("    always @(posedge RACK) begin\n")
        self.source.write("        if (RW) begin\n")
        self.source.write("            WREQ <= 1'b1;\n")
        self.source.write("        end\n")
        self.source.write("    end\n")
        self.source.write("    always @(negedge ACK) begin\n")
        self.source.write("        if (i<4) begin\n")
        self.source.write("            if (i%2==0) begin\n")
        self.source.write("                DATA <= #{0} {1}'b{2};\n".format(delay, dbits, "1"*dbits))
        if self.mask:
            self.source.write("                BM <= #{0} {1}'b{2};\n".format(delay, dbits, "10"*(dbits//2)))
        
        self.source.write("                ADDR <= #{0} {1}'b{2};\n".format(delay, abits, "1"*abits)) 
        self.source.write("            end else if (i%2==1) begin\n")
        self.source.write("                 ADDR <= #{0} {1}'b{2};\n".format(delay, abits, "0"*abits))
        self.source.write("            end\n")
        self.source.write("            W <= #{0} 1'b1;\n".format(delay))
        self.source.write("            WREQ <= #{0} 1'b1;\n".format(delay))
        self.source.write("        end\n")
        self.source.write("        if (i == 4) begin\n")
        self.source.write("            if (j < 4) begin\n")
        self.source.write("                ADDR <= #{0} {1}'b{2};\n".format(delay, abits, "1"*abits))
        self.source.write("                R <= #{0} 1'b1;\n".format(delay))
        self.source.write("                RREQ <= #{0} 1'b1;\n".format(delay))
        self.source.write("            end\n")
        self.source.write("        end\n")
        self.source.write("        if (i == 4 & j ==4) begin\n")
        self.source.write("            if (k < 4) begin\n")
        self.source.write("                if (k%2==0) begin\n")
        self.source.write("                    DATA <= #{0} {1}'b{2};\n".format(delay, dbits, "0"*dbits))
        if self.mask:
            self.source.write("                    BM <= #{0} {1}'b{2};\n".format(delay, dbits, "01"*(dbits//2)))
        
        self.source.write("                    ADDR <= #{0} {1}'b{2};\n".format(delay, abits, "1"*abits)) 
        self.source.write("                end else if (k%2==1) begin\n")
        self.source.write("                    ADDR <= #{0} {1}'b{2};\n".format(delay, abits, "0"*abits)) 
        self.source.write("                end\n")
        self.source.write("                RW <= #{0} 1'b1;\n".format(delay))
        self.source.write("                RREQ<= #{0} 1'b1;\n".format(delay))
        self.source.write("            end\n")
        self.source.write("        end\n")
        self.source.write("    end\n")
        self.source.write("endmodule\n")
        self.source.close()        
        
    def cosim_config(self):
        """ Function to write cosim configuration file. """
        
        self.cosim.write("\n")
        self.cosim.write("    choose finesim test.sp;\n")
        self.cosim.write("    use_spice -cell wrapper;\n")
        self.cosim.write("    set bus_format <%d>;\n")
        self.cosim.close()

    def run_sim(self, load, slew):
        """Run Finesim & VCS in batch mode and output rawfile to parse."""
        
        self.dut_generator(self.addr_bit, self.data_bit, load, self.name, self.w_per_row, self.num_rows)
        self.spice_deck(slew, load)
        self.verilog_testbench(self.addr_bit, self.data_bit)
        self.source_generator(self.addr_bit, self.data_bit, tech.spice["inv_delay"], slew)
        self.cosim_config()

        self.make.write("\n")
        self.make.write("all:\n")
        self.make.write("\tvcs -full64 -ad=setup.init test.v\n")
        self.make.write("\t./simv 2>&1 | tee -i simv.log\n")
        self.make.write("clean:\n")
        self.make.write("\trm -rf ucli.key\n")
        self.make.write("\trm -rf simv.log\n")
        self.make.write("\trm -rf simv.daidir\n")
        self.make.write("\trm -rf simv\n")
        self.make.write("\trm -rf nsda_cosim.sp\n")
        self.make.close()
        
         #if n/p transistor is a subcircuit in this technology, replace M to X for transistor names in spice files
        if tech.info["tx_is_subckt"]:
            for myfile in ["test.sp", "dut.sp", self.name+".sp"]:
                self.edit_netlist(myfile)

       
        for myfile in ["setup.init", "test.sp", "test.v", "source.v", "dut.sp", "Makefile", self.name+".sp"]:
            filename="{0}{1}".format(OPTS.AMC_temp, myfile)
            while not path.exists(filename):
                time.sleep(1)
            else:
                os.chmod(filename, 0o777)
        
        os.chdir(OPTS.AMC_temp)
        spice_stdout = open("{0}spice_stdout.log".format(OPTS.AMC_temp), 'w')
        spice_stderr = open("{0}spice_stderr.log".format(OPTS.AMC_temp), 'w')


        retcode = subprocess.call("make", shell=True, stdout=spice_stdout, stderr=spice_stderr)
        spice_stdout.close()
        spice_stderr.close()

        if (retcode > 1):
            debug.error("Spice simulation error: ", -1)


        filename="{0}{1}".format(OPTS.AMC_temp, "test.mt0")
        while not path.exists(filename):
                time.sleep(1)
        
        #Parse the test.mt0 file to repoert delay and power values.
        write_delay = charutils.parse_output("test", "write_delay")
        read_delay = charutils.parse_output("test", "read_delay")
        read_write_delay = charutils.parse_output("test", "read_write_delay")
        slew_hl = charutils.parse_output("test", "slew_hl")
        slew_lh = charutils.parse_output("test", "slew_lh")
        leakage_power = charutils.parse_output("test", "leakage_power")
        write_power = charutils.parse_output("test", "write_power")
        read_power = charutils.parse_output("test", "read_power")
        read_write_power = charutils.parse_output("test", "read_write_power")
        
        self.result = {"write_delay_lh" : write_delay*(10**9),
                       "write_delay_hl" : write_delay*(10**9),
                       "read_delay_lh" : read_delay*(10**9),
                       "read_delay_hl" : read_delay*(10**9),
                       "read_write_delay_lh" : read_write_delay*(10**9),
                       "read_write_delay_hl" : read_write_delay*(10**9),
                       "slew_hl" : slew_hl*(10**9),
                       "slew_lh" : slew_lh*1e9,
                       "leakage_power" : leakage_power*(10**3),
                       "read_power" : read_power*(10**3),
                       "write_power" : write_power*(10**3),
                       "read_write_power" : read_write_power*(10**3)}
        return self.result
    
    def edit_netlist(self, myfile):
        """ Edit the SPICE netlist if transistor is a subckt and should start with letter X instead of M"""
        
        filename="{0}{1}".format(OPTS.AMC_temp, myfile)
        edited_spfile=filename

        debug.info(1,"Editing transistor name to start with X instaed of M")
        # Load the file into a buffer for performance
        sp = open(filename, "r")
        self.spice = sp.readlines()
        for i in range(len(self.spice)):
            self.spice[i] = self.spice[i].rstrip(" \n")
        self.sp_buffer = self.spice
                
        new_buffer=[]
        for line in self.sp_buffer:
            x = line.find("M", 0, 1)
            if x != -1:
                line = "X"+line
                new_buffer.append(line)
            else:
                new_buffer.append(line)

        self.sp_buffer = new_buffer
        sp = open(edited_spfile, "w")
        sp.write("\n".join(self.sp_buffer))
        

    def create_buffer(self, size=[2,2], beta=2):
        """Generates buffer for top level signals (only for sim purposes). 
           Size is pair for PMOS, NMOS width multiple. It includes a beta of 2."""

        self.dut.write(".subckt test_buffer in out {0} {1}\n".format(self.vdd_name, self.gnd_name))
        self.dut.write("Mpinv1 out_inv in {0} {0} {1} w={2}u l={3}u\n".format(self.vdd_name,
                                                                               self.pmos_name,
                                                                               beta * size[0] * self.minwidth_tx,
                                                                               self.minlength_tx))
        self.dut.write("Mninv1 out_inv in {0} {0} {1} w={2}u l={3}u\n".format(self.gnd_name,
                                                                               self.nmos_name,
                                                                               size[0] * self.minwidth_tx,
                                                                               self.minlength_tx))
        self.dut.write("Mpinv2 out out_inv {0} {0} {1} w={2}u l={3}u\n".format(self.vdd_name,
                                                                                self.pmos_name,
                                                                                beta * size[1] * self.minwidth_tx,
                                                                                self.minlength_tx))
        self.dut.write("Mninv2 out out_inv {0} {0} {1} w={2}u l={3}u\n".format(self.gnd_name,
                                                                                self.nmos_name,
                                                                                size[1] * self.minwidth_tx,
                                                                                self.minlength_tx))
        self.dut.write(".ends test_buffer\n\n")


    def add_in_buffer(self, signal_list):
        """Adds buffers to each top level signal that is in signal_list (only for sim purposes)"""
        
        for signal in signal_list:
            self.dut.write("X{0}_buffer {0} {0}_buf {1} {2} test_buffer\n".format(signal,
                                                                                self.vdd_name,
                                                                                self.gnd_name))
    def add_out_buffer(self, signal_list):
        """Adds buffers to each top level signal that is in signal_list (only for sim purposes)"""
        
        for signal in signal_list:
            self.dut.write("X{0}_buffer {0}_buf {0} {1} {2} test_buffer\n".format(signal,
                                                                                self.vdd_name,
                                                                                self.gnd_name))


    def add_cap_load(self, signal_list, load):
        """Adds capacitor load to top level signal that is in signal_list (only for sim purposes)"""
        
        for signal in signal_list:
            self.dut.write("C{0} {0} 0 {1}fF\n".format(signal, load))

