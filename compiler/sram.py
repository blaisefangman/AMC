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


import sys
import datetime
import getpass
import design
import lef
import async_verilog
import debug
import contact
from math import log
from vector import vector
from globals import OPTS, print_time
from multi_bank import multi_bank
from split_merge_control import split_merge_control
from bitcell import bitcell
from tech import amc_layer_names

   
class sram(design.design, lef.lef, async_verilog.verilog):
    """ Dynamically generated two level multi-bank asynchronous SRAM. """

    def __init__(self, word_size, words_per_row, num_rows, num_subanks, 
                 branch_factors, bank_orientations, mask, power_gate, name):
        
        design.design.name_map=[]
        start_time = datetime.datetime.now()
        design.design.__init__(self, name)
        lef.lef.__init__(self, amc_layer_names)

        self.w_size = word_size
        self.w_per_row = words_per_row
        self.num_rows = num_rows
        self.num_sbank = num_subanks
        self.num_obank = branch_factors[0]
        self.num_ibank = branch_factors[1]
        self.obank_orien = bank_orientations[0]
        self.ibank_orien = bank_orientations[1]
        self.mask = mask
        self.power_gate=power_gate

        if self.num_obank > 1:
            self.two_level_bank = True
        else:
            self.two_level_bank = False
        
        self.compute_sizes()
        self.add_pins()
        self.create_layout()
        self.offset_all_coordinates()

        self.bitcell = bitcell()

        self.total_bits = self.num_rows*self.num_sbank*self.w_size*\
                          self.w_per_row*self.num_ibank*self.num_obank
        efficiency = 100*((self.total_bits*self.bitcell.width*\
                      self.bitcell.height)/(self.width*self.height))
        
    def compute_sizes(self):
        """ Compute the address sizes """
        
        row_addr_size = int(log(self.num_rows, 2))
        subank_addr_size = int(log(self.num_sbank, 2))
        col_mux_addr_size = int(log(self.w_per_row, 2))
        self.inbank_addr_size = subank_addr_size + row_addr_size + col_mux_addr_size + int(log(self.num_ibank, 2))
        outbank_addr_size = int(log(self.num_obank, 2))
        self.addr_size = self.inbank_addr_size + outbank_addr_size
        self.via_yshift =  0.5*abs(contact.m1m2.second_layer_height-contact.m1m2.first_layer_height)

    def add_pins(self):
        """ Add pins for entire SRAM. """

        for i in range(self.w_size):
                self.add_pin("data_in[{0}]".format(i),"INPUT")
        for i in range(self.w_size):
                self.add_pin("data_out[{0}]".format(i),"OUTPUT")
        for i in range(self.addr_size):
            self.add_pin("addr[{0}]".format(i),"INPUT")
        if self.mask:
            for i in range(self.w_size):
                self.add_pin("bm[{0}]".format(i),"INPUT")
        self.add_pin_list(["reset", "r", "w",  "rw"],"INPUT")
        self.add_pin_list(["ack", "rack"], "OUTPUT")
        self.add_pin_list(["rreq", "wreq"],"INPUT")
        self.add_pin_list(["wack"],"OUTPUT")
        if self.power_gate:
            self.add_pin("sleep","INPUT")

        self.add_pin("vdd","POWER")
        self.add_pin("gnd","GROUND")

    def create_layout(self):
        """ Layout creation """
        
        self.create_modules()

        if self.num_obank == 1:
            self.add_single_inbank_module()
        elif self.num_obank == 2:
            self.add_two_outbank_modules()
        elif self.num_obank == 4:
            self.add_four_outbank_modules()
        else:
            debug.error("Invalid number of banks! only 1, 2 and 4 banks are allowed",-1)

    def create_modules(self):
        """ Create all the modules that will be used """
        
        # Create the inbank module (up to four are instantiated)
        self.inbank = multi_bank(word_size=self.w_size, words_per_row=self.w_per_row, 
                                 num_rows=self.num_rows, num_subanks=self.num_sbank, 
                                 num_banks=self.num_ibank, orientation=self.ibank_orien, 
                                 two_level_bank=self.two_level_bank, mask=self.mask,
                                 power_gate=self.power_gate, name="inbank")
        self.add_mod(self.inbank)

        if self.num_obank > 1:
            self.out_sm_ctrl = split_merge_control(num_banks=self.num_obank, 
                                                   name="out_split_merge_ctrl")
            self.add_mod(self.out_sm_ctrl)

    def add_inbanks(self, num, pos, x_flip, y_flip):
        """ Place an inner multi-bank module at the given position with orientations """

        # x_flip ==  1 --> no flip in x_axis
        # x_flip == -1 --> flip in x_axis
        # y_flip ==  1 --> no flip in y_axis
        # y_flip == -1 --> flip in y_axis

        # x_flip and y_flip are used for position translation

        if x_flip == -1 and y_flip == -1:
            inbank_rotation = 180
        else:
            inbank_rotation = 0

        if x_flip == y_flip:
            inbank_mirror = "R0"
        elif x_flip == -1:
            inbank_mirror = "MX"
        elif y_flip == -1:
            inbank_mirror = "MY"
        else:
            inbank_mirror = "R0"
            
        inbank_inst=self.add_inst(name="inbank{0}".format(num),
                                  mod=self.inbank,
                                  offset=pos,
                                  mirror=inbank_mirror,
                                  rotate=inbank_rotation)
        temp = []
        for i in range(self.w_size):
            temp.append("data_in[{0}]".format(i))
        for i in range(self.w_size):
            temp.append("data_out[{0}]".format(i))
        for i in range(self.inbank_addr_size):
            temp.append("addr[{0}]".format(i))
        if self.mask:
            for i in range(self.w_size):
                temp.append("bm[{0}]".format(i))
        if self.num_obank == 1:
            temp.extend(["reset", "r", "w",  "rw", "ack", "rack", "rreq", "wreq", "wack"])
        else:
            temp.extend(["reset", "r", "w",  "rw", "pre_ack", "pre_rack", "rreq", "wreq", "pre_wack"])
            temp.extend(["sel[{0}]".format(num), "ack{0}".format(num), "ack_b{0}".format(num), 
                         "ack_b", "rw_merge", "rreq", "wreq", "rack"])
        if self.power_gate:
            temp.append("sleep")
        temp.extend(["vdd", "gnd"])
        self.connect_inst(temp)

        return inbank_inst

    def compute_bus_sizes(self):
        """ Compute the bus widths shared between two and four bank SRAMs """
        
        self.pow_width = self.inbank.pow_width
        self.pow_pitch = self.inbank.pow_pitch
        self.pitch = max(self.m1_pitch, self.m2_pitch)
        self.num_via = self.inbank.num_via
        
        #"r", "w",  "rw", "ack", "rack", "rreq", "wreq", "wack"
        self.control_size = 8
        self.gap = 5*self.pitch
        
        # horizontal bus size (din, dout, addr, crl, sel, 
        # s/m input (2*num_outbanks), s/m ctrl (5), and reset)
        self.num_h_line = self.addr_size + self.control_size + self.w_size +\
                          self.num_obank + 2*self.num_obank + 5 + 1
        
        if self.obank_orien == "H":
            self.data_bus_width = 2*self.inbank.width + 4*self.gap + 4*self.pow_pitch+\
                                  self.out_sm_ctrl.height+self.m1_width
        if self.obank_orien == "V":
            self.data_bus_width = self.inbank.width + self.gap + self.out_sm_ctrl.height+ \
                                  4*self.pow_pitch + self.pitch+self.m1_width
        
        
        self.hbus_height = self.pitch*self.num_h_line + 2*self.pow_pitch
    
    def add_single_inbank_module(self):
        """ This adds a single bank SRAM (No orientation or offset) """
        
        self.inbank_inst = self.add_inbanks(0, [0, 0], 1, 1)
        self.add_single_inbank_pins()
        self.width = self.inbank_inst.width
        self.height = self.inbank_inst.height

    def add_two_outbank_modules(self):
        """ This adds two inbank SRAM """
        
        self.compute_two_outbank_offsets()
        self.add_two_outbanks()
        self.add_busses()
        self.route_outbanks()
        self.width = self.inbank_inst[1].ur().x + self.out_sm_ctrl.height + self.m1_width
        self.height = self.inbank_inst[1].ur().y
        if (self.ibank_orien == "V" and self.obank_orien == "H"):
            self.height = self.dout1_off.y + (self.w_size+1)*self.pitch
        if (self.ibank_orien == "V" and self.obank_orien == "V"):
            self.height = self.dout2_off.y + (self.w_size+1)*self.pitch
            self.width= self.width+ (self.w_size+1)*self.pitch
            

    def add_four_outbank_modules(self):
        """ This adds four inbank SRAM """

        self.compute_four_outbank_offsets()
        self.add_four_outbanks()
        self.add_busses()
        self.route_outbanks()
        
        if self.obank_orien == "H":
            self.width = self.inbank_inst[3].ur().x+ self.out_sm_ctrl.height+\
                         self.pitch*(self.w_size+1) 
            self.height = self.inbank_inst[3].ur().y
            if self.ibank_orien == "V" :
                self.height = self.dout2_off.y + (self.w_size+1)*self.pitch

        if self.obank_orien == "V":
            self.width = self.inbank_inst[3].ur().x+ self.out_sm_ctrl.height+ \
                         self.pitch*(2*self.w_size+self.inbank_addr_size+4) 
            self.height = self.inbank_inst[3].ur().y
            if self.mask:
                self.width = self.width + self.pitch*(1*self.w_size)
            
            if self.ibank_orien == "V" :
                self.height = self.dout2_off.y+ (self.w_size+1)*self.pitch
        
    def compute_two_outbank_offsets(self):
        """ Compute the buses offsets based on orientation of inner banks and outter banks"""

        self.compute_bus_sizes()
        h_off = self.out_sm_ctrl.height
        if self.obank_orien == "H":
            self.pow1_off = vector(-h_off, 0)
            self.din1_off = vector(-h_off, 2*self.pow_pitch)
            
            if self.ibank_orien == "H":
                self.dout1_off = vector(-h_off, self.din1_off.y + self.w_size*self.pitch)
                self.reset1_off = vector(-h_off, self.dout1_off.y + self.w_size*self.pitch)
            
            if self.ibank_orien == "V":
                self.dout1_off = vector(-h_off, self.inbank.height+self.hbus_height+ 2*self.gap+2*self.pow_pitch)
                self.reset1_off = vector(-h_off, self.din1_off.y + self.w_size*self.pitch)
            
            self.addr_bus_off = vector(-h_off, self.reset1_off.y + self.pitch)
            if self.power_gate:        
                self.sleep1_off = vector(-h_off, self.reset1_off.y + self.pitch)
                self.addr_bus_off = vector(-h_off, self.sleep1_off.y + self.pitch)

        if self.obank_orien == "V":
            if self.ibank_orien == "H":
                self.pow1_off = vector(-h_off, self.inbank.height + self.gap)
                self.din1_off = vector(-h_off, self.pow1_off.y + 2*self.pow_pitch)
                self.dout1_off = vector(-h_off, self.din1_off.y + self.w_size*self.pitch)
                self.reset1_off = vector(-h_off, self.dout1_off.y + self.w_size*self.pitch)
            
            if self.ibank_orien == "V":
                self.pow1_off = vector(-h_off, self.inbank.height + 2*self.gap + self.w_size*self.pitch)
                self.din1_off = vector(-h_off, self.pow1_off.y + 2*self.pow_pitch)
                self.dout1_off = vector(-h_off, 0)
                self.dout2_off = vector(-h_off, self.hbus_height+ 2*self.gap + self.w_size*self.pitch+ \
                                         2*(self.inbank.height+self.gap+self.pow_pitch))
                self.reset1_off = vector(-h_off, self.din1_off.y + self.w_size*self.pitch)
            
            self.addr_bus_off = vector(-h_off, self.reset1_off.y + self.pitch)
            if self.power_gate:        
                self.sleep1_off = vector(-h_off, self.reset1_off.y + self.pitch)
                self.addr_bus_off = vector(-h_off, self.sleep1_off.y + self.pitch)
        
        
        self.sel_bus_off = vector(-h_off, self.addr_bus_off.y + self.addr_size*self.pitch)
        self.sm_in_off = vector(-h_off, self.sel_bus_off.y + self.num_obank*self.pitch)
        self.sm_ctrl_bus_off = vector(-h_off, self.sm_in_off.y + (2*self.num_obank)*self.pitch)
        self.ctrl_bus_off= vector(-h_off, self.sm_ctrl_bus_off.y + 5*self.pitch)


    def compute_four_outbank_offsets(self):
        """ Compute the buses offsets based on orientation of inner banks and outter banks"""
        
        self.compute_bus_sizes()
        h_off = self.out_sm_ctrl.height
        if self.obank_orien == "H":
            if self.ibank_orien == "H":
                self.pow1_off = vector(-h_off, self.inbank.height + self.gap)
                self.din1_off = vector(-h_off, self.pow1_off.y+2*self.pow_pitch)
                self.dout1_off = vector(-h_off, self.din1_off.y + self.w_size*self.pitch)
                self.reset1_off = vector(-h_off, self.dout1_off.y + self.w_size*self.pitch)
            if self.ibank_orien == "V":
                self.pow1_off = vector(-h_off, self.inbank.height + 2*self.gap + self.w_size*self.pitch)
                self.din1_off = vector(-h_off, self.pow1_off.y + 2*self.pow_pitch)
                self.reset1_off = vector(-h_off, self.din1_off.y + self.w_size*self.pitch)
                self.dout1_off = vector(-h_off, 0)
                self.dout2_off = vector(-h_off,self.hbus_height+self.gap+ self.w_size*self.pitch+ \
                                            2*(self.inbank.height+ self.gap+2*self.pow_pitch))
        if self.obank_orien == "V":
            if self.ibank_orien == "H":
                self.pow1_off = vector(-h_off, self.inbank.height + self.gap)
                self.din1_off = vector(-h_off, self.pow1_off.y + 2*self.pow_pitch)
                self.dout1_off = vector(-h_off, self.din1_off.y +  self.w_size*self.pitch)
                self.reset1_off = vector(-h_off, self.dout1_off.y + self.w_size*self.pitch)
                self.pow2_off = vector(-h_off, 3*(self.inbank.height + self.gap)+ self.gap +\
                                        self.w_size*self.pitch+self.hbus_height+ 2*self.pow_pitch)
                self.din2_off = vector(-h_off, self.pow2_off.y + 2*self.pow_pitch)
                self.dout2_off = vector(-h_off, self.din2_off.y + self.w_size*self.pitch)
                self.reset2_off = vector(-h_off, self.dout2_off.y + self.w_size*self.pitch)

            if self.ibank_orien == "V":
                self.pow1_off = vector(-h_off, self.inbank.height + 2*self.gap + self.w_size*self.pitch)
                self.din1_off = vector(-h_off, self.pow1_off.y + 2*self.pow_pitch)
                self.reset1_off = vector(-h_off, self.din1_off.y +  self.w_size*self.pitch)
                self.dout1_off = vector(-h_off, 0)
                
                self.pow2_off = vector(-h_off, 3*(self.inbank.height +2*self.gap)+\
                                       2*self.w_size*self.pitch+self.hbus_height)
                self.din2_off = vector(-h_off, self.pow2_off.y + 2*self.pow_pitch)
                self.reset2_off = vector(-h_off, self.din2_off.y +  self.w_size*self.pitch)
                self.dout2_off = vector(-h_off, 2*(self.hbus_height+ self.w_size*self.pitch) +\
                                        4*(self.inbank.height+2*self.gap+self.pow_pitch))
                self.dout_bus3_off = vector(-h_off, self.hbus_height+ self.w_size*self.pitch +\
                                            2*(self.inbank.height+2*self.gap+self.pow_pitch))

            self.addr_bus2_off = vector(-h_off, self.reset2_off.y + self.pitch)
            if self.power_gate:
                self.sleep2_off= vector(-h_off, self.reset2_off.y + self.pitch)
                self.addr_bus2_off = vector(-h_off, self.sleep2_off.y + self.pitch)
            self.sel_bus2_off = vector(-h_off, self.addr_bus2_off.y + self.addr_size*self.pitch)
            self.split_merge_input2_off = vector(-h_off, self.sel_bus2_off.y + self.num_obank*self.pitch)
            self.split_merge_ctrl_bus2_off = vector(-h_off, self.split_merge_input2_off.y +\
                                                    (2*self.num_obank)*self.pitch)
            self.ctrl_bus2_off= vector(-h_off, self.split_merge_ctrl_bus2_off.y + 5*self.pitch)
        
        self.addr_bus_off = vector(-h_off, self.reset1_off.y + self.pitch)
        if self.power_gate:
            self.sleep1_off= vector(-h_off, self.reset1_off.y + self.pitch)
            self.addr_bus_off = vector(-h_off, self.sleep1_off.y + self.pitch)
        
        self.sel_bus_off = vector(-h_off, self.addr_bus_off.y + self.addr_size*self.pitch)
        self.sm_in_off = vector(-h_off, self.sel_bus_off.y + self.num_obank*self.pitch)
        self.sm_ctrl_bus_off = vector(-h_off, self.sm_in_off.y + (2*self.num_obank)*self.pitch)
        self.ctrl_bus_off= vector(-h_off, self.sm_ctrl_bus_off.y + 5*self.pitch)


    def add_two_outbanks(self):
        """ Add the two outter banks and control module"""
        
        if self.obank_orien == "H":
            x_off = self.inbank.width + 2*self.gap 
            if self.ibank_orien == "H":
                y_off = self.hbus_height + self.gap + \
                        self.w_size*self.pitch + 2*self.pow_pitch
            if self.ibank_orien == "V":
                y_off = self.hbus_height + self.gap + 2*self.pow_pitch

            # Placement of inbanks 0 (left)
            inbanks_pos_0 = vector(x_off, y_off)
            self.inbank_inst=[self.add_inbanks(0, inbanks_pos_0, 1, -1)]

            # Placement of inbanks 1 (right)
            inbanks_pos_1 = vector(x_off+2*self.gap+4*self.pow_pitch, y_off)
            self.inbank_inst.append(self.add_inbanks(1, inbanks_pos_1, 1, 1))

        if self.obank_orien == "V":
            x_off= self.gap + 4*self.pow_pitch
            if self.ibank_orien == "H":
                y_off1 = self.inbank.height
                y_off2= y_off1 + self.hbus_height + self.w_size*self.pitch+\
                        2*(self.gap + self.pow_pitch)
            if self.ibank_orien == "V":
                y_off1 = self.inbank.height + self.gap + self.w_size*self.pitch
                y_off2= y_off1 + self.hbus_height + 2*(self.gap + self.pow_pitch)
            
            # Placement of inbanks 0 (bottom)
            inbanks_pos_0= vector(x_off,y_off1)
            self.inbank_inst= [self.add_inbanks(0, inbanks_pos_0, -1, 1)]

            # Placement of inbanks 1 (top)
            inbanks_pos_1= vector(x_off, y_off2)
            self.inbank_inst.append(self.add_inbanks(1, inbanks_pos_1, 1, 1))

        out_sm_ctrl_off = vector(0,inbanks_pos_1.y)
        self.out_sm_ctrl_inst = self.add_inst(name="out_split_merge_ctrl", 
                                              mod=self.out_sm_ctrl, 
                                              offset=out_sm_ctrl_off,
                                              mirror= "R0",
                                              rotate = 90)
        temp =[]
        temp.extend(["r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"])
        for i in range(self.num_obank):
            temp.append("ack{0}".format(i))
            temp.append("ack_b{0}".format(i))
        temp.extend(["pre_ack", "pre_wack", "pre_rack", "rw_merge"])        
        temp.extend(["ack_b", "addr[{0}]".format(self.addr_size-1), "sel[0]", "sel[1]"])
        temp.extend(["vdd", "vdd","gnd"])
        self.connect_inst(temp)

    def add_four_outbanks(self):
        """ Add the four outter banks and control module"""
        
        if self.obank_orien == "H":
            x_off = self.inbank.width + 2*self.gap
            if self.ibank_orien == "H":
                y_off1 = self.inbank.height+ self.hbus_height + 2*self.gap+ \
                        self.w_size*self.pitch + 2*self.pow_pitch
                y_off2 = self.inbank.height
            if self.ibank_orien == "V":
                y_off1 = self.inbank.height+ self.hbus_height + 3*self.gap+ \
                        self.w_size*self.pitch + 2*self.pow_pitch
                y_off2 = self.inbank.height+self.w_size*self.pitch+self.gap
                
            # Placement of inbanks 0 (bottom left)
            inbanks_pos_0= vector(x_off,y_off2)
            self.inbank_inst=[self.add_inbanks(0, inbanks_pos_0, -1, -1)]

            # Placement of bank 1 (bottom right)
            inbanks_pos_1= vector(x_off+2*self.gap+ 4*self.pow_pitch, y_off2)
            self.inbank_inst.append(self.add_inbanks(1, inbanks_pos_1, -1, 1))

            # Placement of bank 2 (upper left)
            inbanks_pos_2= vector(x_off, y_off1)
            self.inbank_inst.append(self.add_inbanks(2, inbanks_pos_2, 1, -1))

            # Placement of bank 3 (upper right)
            inbanks_pos_3= vector(inbanks_pos_1.x, y_off1)
            self.inbank_inst.append(self.add_inbanks(3, inbanks_pos_3, 1, 1))
        
        if self.obank_orien == "V":
            x_off = self.gap+ 4*self.pow_pitch
            if self.ibank_orien == "H":
                y_off1 = self.inbank.height
                y_off2 = y_off1+ self.hbus_height + 2*self.gap+  self.w_size*self.pitch + 2*self.pow_pitch
                y_off3 = 3*self.inbank.height+ 2*(self.gap+self.pow_pitch)+ \
                        self.hbus_height + self.w_size*self.pitch + self.gap
                y_off4 =  y_off3+ self.hbus_height +self.w_size*self.pitch+ 2*(self.pow_pitch+self.gap)
            if self.ibank_orien == "V":
                y_off1 = self.inbank.height +self.w_size*self.pitch+self.gap
                y_off2 = y_off1+ self.hbus_height + 2*(self.gap+ self.pow_pitch)
                y_off3 = 3*self.inbank.height+ 5*self.gap+ 2*self.pow_pitch+ \
                         self.hbus_height + 2*self.w_size*self.pitch
                y_off4 = y_off3+  self.hbus_height + 2*(self.pow_pitch+self.gap)

            # Placement of bank 0 (lowest)
            inbanks_pos_0= vector(x_off,y_off1)
            self.inbank_inst=[self.add_inbanks(0, inbanks_pos_0, -1, 1)]

            # Placement of bank 1 
            inbanks_pos_1= vector(x_off,y_off2)
            self.inbank_inst.append(self.add_inbanks(1, inbanks_pos_1, 1, 1))

            # Placement of bank 2 
            inbanks_pos_2= vector(x_off,y_off3)
            self.inbank_inst.append(self.add_inbanks(2, inbanks_pos_2, -1, 1))

            # Placement of bank 3 (topmost)
            inbanks_pos_3= vector(x_off,y_off4)
            self.inbank_inst.append(self.add_inbanks(3, inbanks_pos_3, 1, 1))

        if self.obank_orien == "H":
            out_sm_ctrl_off = vector(0,inbanks_pos_2.y)
        if self.obank_orien == "V":
            out_sm_ctrl_off = vector(0,inbanks_pos_3.y)
        self.out_sm_ctrl_inst= self.add_inst(name="out_split_merge_ctrl", 
                                             mod=self.out_sm_ctrl, 
                                             offset=out_sm_ctrl_off,
                                             mirror= "R0",
                                             rotate = 90)

        temp =[]
        temp.extend(["r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"])
        for i in range(self.num_obank):
            temp.append("ack{0}".format(i))
            temp.append("ack_b{0}".format(i))
        
        temp.extend(["pre_ack", "pre_wack", "pre_rack", "rw_merge", "ack_b"])
        for i in range(int(log(self.num_obank,2))):
            temp.append("addr[{0}]".format(self.addr_size-2+i))

        for i in range(self.num_obank):
            temp.append("sel[{0}]".format(i))

        temp.extend(["vdd","vdd","gnd"])
        self.connect_inst(temp)


    def add_single_inbank_pins(self):
        """ Add pins for Single outtter bank SRAM """

        ctrl_pins = ["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"]
        if self.power_gate:
            ctrl_pins.append("sleep")

        for i in range(len(ctrl_pins)):
            pin = self.inbank_inst.get_pin(ctrl_pins[i])
            self.add_layout_pin(text=ctrl_pins[i],
                                layer = pin.layer,
                                offset = pin.ll(),
                                width = pin.width(),
                                height = pin.height())
        for i in range(self.addr_size):
            pin = self.inbank_inst.get_pin("addr[{0}]".format(i))
            self.add_layout_pin(text="addr[{0}]".format(i),
                                layer = pin.layer,
                                offset = pin.ll(),
                                width = pin.width(),
                                height = pin.height())
        for i in range(self.w_size):
            pin = self.inbank_inst.get_pin("din[{0}]".format(i))
            self.add_layout_pin(text="data_in[{0}]".format(i),
                                layer = pin.layer,
                                offset = pin.ll(),
                                width = pin.width(),
                                height = pin.height())
            pin = self.inbank_inst.get_pin("dout[{0}]".format(i))
            self.add_layout_pin(text="data_out[{0}]".format(i),
                                layer = pin.layer,
                                offset = pin.ll(),
                                width = pin.width(),
                                height = pin.height())
            if self.mask:
                pin = self.inbank_inst.get_pin("bm[{0}]".format(i))
                self.add_layout_pin(text="bm[{0}]".format(i),
                                    layer = pin.layer,
                                    offset = pin.ll(),
                                    width = pin.width(),
                                    height = pin.height())


        power_pins = ["vdd","gnd"]
        for i in power_pins:
            for pin in self.inbank_inst.get_pins(i):
                self.add_layout_pin(text=i,
                                    layer = pin.layer,
                                    offset = pin.ll(),
                                    width = pin.width(),
                                    height = pin.height())

    def add_busses(self):
        """ Add the horizontal busses """
        
        # Horizontal power rails
        power_rail_names= ["vdd", "gnd"]
        for i in range(2):
            self.add_rect(layer="m3", 
                          offset=self.pow1_off+vector(0, i*self.pow_pitch), 
                          width=self.data_bus_width, 
                          height=self.pow_width)
            self.add_layout_pin(text=power_rail_names[i], 
                                layer="m3", 
                                offset=self.pow1_off+vector(0, i*self.pow_pitch), 
                                width=self.data_bus_width, 
                                height=self.pow_width)
        
        data_in_names=["data_in[{0}]".format(i) for i in range(self.w_size)]
        self.data_in1_bus_pos = self.create_bus(layer="m1",
                                                pitch=self.pitch,
                                                offset=self.din1_off,
                                                names=data_in_names,
                                                length=self.data_bus_width,
                                                vertical=False,
                                                make_pins=True)
        if self.mask:
            bm_names=["bm[{0}]".format(i) for i in range(self.w_size)]
            self.bm1_bus_pos = self.create_bus(layer="m3",
                                               pitch=self.pitch,
                                               offset=self.din1_off,
                                               names=bm_names,
                                               length=self.data_bus_width,
                                               vertical=False,
                                               make_pins=True)


        data_out_names=["data_out[{0}]".format(i) for i in range(self.w_size)]
        self.data_out1_bus_pos = self.create_bus(layer="m1",
                                                 pitch=self.pitch,
                                                 offset=self.dout1_off,
                                                 names=data_out_names,
                                                 length=self.data_bus_width,
                                                 vertical=False,
                                                 make_pins=True)



        reset_name = ["reset"]
        self.H_ctrl_bus_pos = self.create_bus(layer="m1",
                                              pitch=self.pitch,
                                              offset=self.reset1_off,
                                              names=reset_name,
                                              length=self.data_bus_width,
                                              vertical=False,
                                              make_pins=True)
        if self.power_gate:
            self.H_ctrl_bus_pos = self.create_bus(layer="m1",
                                                  pitch=self.pitch,
                                                  offset=self.sleep1_off,
                                                  names=["sleep"],
                                                  length=self.data_bus_width,
                                                  vertical=False,
                                                  make_pins=True)
        

        addr_names=["addr[{0}]".format(i) for i in range(self.addr_size)]
        self.H_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                   pitch=self.pitch,
                                                   offset=self.addr_bus_off,
                                                   names=addr_names,
                                                   length=self.data_bus_width,
                                                   vertical=False,
                                                   make_pins=True))
        sel_names=["sel[{0}]".format(i) for i in range(self.num_obank)]
        self.H_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                   pitch=self.pitch,
                                                   offset=self.sel_bus_off,
                                                   names=sel_names,
                                                   length=self.data_bus_width,
                                                   vertical=False,
                                                   make_pins=True))

        for i in range(self.num_obank):
            self.bank_split_merge_input_names = ["ack{0}".format(i), 
                                                 "ack_b{0}".format(i)]
            self.H_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                       pitch=self.pitch,
                                                       offset=self.sm_in_off+\
                                                       vector(0,2*i*self.pitch),
                                                       names=self.bank_split_merge_input_names,
                                                       length=self.data_bus_width,
                                                       vertical=False,
                                                       make_pins=True))

        bank_split_mrg_bus_names = ["pre_wack", "pre_rack", "rw_merge", "pre_ack", "ack_b"]
        self.H_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                   pitch=self.pitch,
                                                   offset=self.sm_ctrl_bus_off,
                                                   names=bank_split_mrg_bus_names,
                                                   length=self.data_bus_width,
                                                   vertical=False,
                                                   make_pins=True))


        ctrl_names=["wack", "wreq",  "rreq", "rack", "ack", "rw", "w", "r"]
        self.H_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                   pitch=self.pitch,
                                                   offset=self.ctrl_bus_off,
                                                   names=ctrl_names,
                                                   length=self.data_bus_width,
                                                   vertical=False,
                                                   make_pins=True))


        if (self.obank_orien == "V" and  self.num_obank == 4):
            power_rail_names= ["vdd", "gnd"]
            for i in range(2):
                self.add_rect(layer="m3", 
                               offset=self.pow2_off+vector(0, i*self.pow_pitch), 
                               width=self.data_bus_width, 
                               height=self.pow_width)
                self.add_layout_pin(text=power_rail_names[i], 
                                    layer="m3", 
                                    offset=self.pow2_off+vector(0, i*self.pow_pitch), 
                                    width=self.data_bus_width, 
                                    height=self.pow_width)

            data_in_names=["data_in[{0}]".format(i) for i in range(self.w_size)]
            self.data_in2_bus_pos = self.create_bus(layer="m1",
                                                    pitch=self.pitch,
                                                    offset=self.din2_off,
                                                    names=data_in_names,
                                                    length=self.data_bus_width,
                                                    vertical=False,
                                                    make_pins=False)
            
            if self.mask:
                bm_names=["data_in[{0}]".format(i) for i in range(self.w_size)]
                self.bm2_bus_pos = self.create_bus(layer="m3",
                                                   pitch=self.pitch,
                                                   offset=self.din2_off,
                                                   names=bm_names,
                                                   length=self.data_bus_width,
                                                   vertical=False,
                                                   make_pins=False)
            

            data_out_names=["data_out[{0}]".format(i) for i in range(self.w_size)]
            self.data_out2_bus_pos = self.create_bus(layer="m1",
                                                     pitch=self.pitch,
                                                     offset=self.dout2_off,
                                                     names=data_out_names,
                                                     length=self.data_bus_width,
                                                     vertical=False,
                                                     make_pins=False)
           
            reset_name = ["reset"]
            self.H2_ctrl_bus_pos = self.create_bus(layer="m1",
                                                   pitch=self.pitch,
                                                   offset=self.reset2_off,
                                                   names=reset_name,
                                                   length=self.data_bus_width,
                                                   vertical=False,
                                                   make_pins=False)
        

            if self.power_gate:
                self.H2_ctrl_bus_pos = self.create_bus(layer="m1",
                                                       pitch=self.pitch,
                                                       offset=self.sleep2_off,
                                                       names=["sleep"],
                                                       length=self.data_bus_width,
                                                       vertical=False,
                                                       make_pins=True)

            addr_names=["addr[{0}]".format(i) for i in range(self.addr_size)]
            self.H2_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                        pitch=self.pitch,
                                                        offset=self.addr_bus2_off,
                                                        names=addr_names,
                                                        length=self.data_bus_width,
                                                        vertical=False,
                                                        make_pins=False))

            sel_names=["sel[{0}]".format(i) for i in range(self.num_obank)]
            self.H2_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                        pitch=self.pitch,
                                                        offset=self.sel_bus2_off,
                                                        names=sel_names,
                                                        length=self.data_bus_width,
                                                        vertical=False,
                                                        make_pins=False))

            for i in range(self.num_obank):
                self.bank_split_merge_input_names = ["ack{0}".format(i), 
                                                     "ack_b{0}".format(i)]
                self.H2_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                            pitch=self.pitch,
                                                            offset=self.split_merge_input2_off+\
                                                            vector(0,2*i*self.pitch),
                                                            names=self.bank_split_merge_input_names,
                                                            length=self.data_bus_width,
                                                            vertical=False,
                                                            make_pins=False))

            bank_split_mrg_bus_names = ["pre_wack", "pre_rack", "rw_merge", "pre_ack", "ack_b"]
            self.H2_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                        pitch=self.pitch,
                                                        offset=self.split_merge_ctrl_bus2_off,
                                                        names=bank_split_mrg_bus_names,
                                                        length=self.data_bus_width,
                                                        vertical=False,
                                                        make_pins=False))


            ctrl_names=["wack", "wreq",  "rreq", "rack", "ack", "rw", "w", "r"]
            self.H2_ctrl_bus_pos.update(self.create_bus(layer="m1",
                                                        pitch=self.pitch,
                                                        offset=self.ctrl_bus2_off,
                                                        names=ctrl_names,
                                                        length=self.data_bus_width,
                                                        vertical=False,
                                                        make_pins=False))

    def route_outbanks(self):
        """ Connect the inputs and outputs of each outer bank to horizontal busses """

        # Data Connections
        if (self.num_obank == 2):
            for k in range(self.num_obank):
                for i in range(self.w_size):
                    pin = self.inbank_inst[k].get_pin("din[{0}]".format(i)).ll()
                    yoff = self.din1_off.y+ i*self.pitch +0.5*self.m1_width
                    din_off = vector(pin.x, yoff)
                    din_height =  pin.y - yoff + self.m1_width
                    self.add_rect(layer="m2", 
                                  offset=din_off, 
                                  width=self.m2_width, 
                                  height=din_height)
                    self.add_via(self.m1_stack, offset=(din_off.x, din_off.y-self.via_yshift))

                    if self.mask:
                        pin=self.inbank_inst[k].get_pin("bm[{0}]".format(i)).ll()
                        yoff = self.din1_off.y+ i*self.pitch +0.5*self.m1_width
                        din_off = vector(pin.x, yoff)
                        din_height =  pin.y -  yoff + self.m1_width
                        self.add_rect(layer="m2", offset=din_off, width=self.m2_width, height=din_height)
                        self.add_via_center(self.m2_stack, offset=(din_off.x+0.5*self.m2_width, din_off.y+0.5*contact.m2m3.width))
    
                    if (self.obank_orien == "H" or self.ibank_orien == "H"): 
                        pin =  self.inbank_inst[k].get_pin("dout[{0}]".format(i)).ll()
                        yoff = self.dout1_off.y+i*self.pitch+0.5*self.m1_width
                        dout_off = vector(pin.x, yoff)
                        dout_height = pin.y - yoff + self.m1_width
                        self.add_rect(layer="m2", 
                                      offset=dout_off, 
                                      width=self.m2_width, 
                                      height=dout_height)
                        self.add_via(self.m1_stack, (dout_off.x, dout_off.y-self.via_yshift))

                    else: 
                        dout_off1 = self.inbank_inst[0].get_pin("dout[{0}]".format(i))
                        dout_off2 = self.inbank_inst[1].get_pin("dout[{0}]".format(i))
                        dout_off1_y = self.dout1_off.y+ i*self.pitch +self.m1_width
                        dout_off2_y = self.dout2_off.y+ i*self.pitch
                        x_off = self.inbank_inst[1].lr().x+(i+1)*self.pitch 
                        self.add_wire(self.m1_stack, [(dout_off1.uc().x,dout_off1.ll().y),
                                      (dout_off1.uc().x,dout_off1_y),
                                      (x_off,dout_off1_y), (x_off,dout_off2_y),
                                      (dout_off1.uc().x,dout_off2_y),
                                      (dout_off2.uc().x,dout_off2.ll().y)], widen_short_wires=False) 

        # Data Connections
        if (self.num_obank == 4 and self.obank_orien == "H"):
            for k in range(self.num_obank):
                for i in range(self.w_size):
                    pin = self.inbank_inst[k].get_pin("din[{0}]".format(i)).ll()
                    yoff = self.din1_off.y+ i*self.pitch + 0.5*self.m1_width
                    din_off = vector(pin.x,  yoff)
                    din_height =  pin.y - yoff + self.m1_width
                    self.add_rect(layer="m2", 
                                  offset=din_off, 
                                  width=self.m2_width, 
                                  height=din_height)
                    self.add_via(self.m1_stack, (din_off.x, din_off.y-self.via_yshift))
                    
                    if self.mask:
                        pin = self.inbank_inst[k].get_pin("bm[{0}]".format(i)).ll()
                        bm_off = vector(pin.x, yoff)
                        bm_height =  pin.y - yoff + self.m1_width
                        self.add_rect(layer="m2", 
                                      offset=bm_off, 
                                      width=self.m2_width, 
                                      height=bm_height)
                        self.add_via_center(self.m2_stack, (bm_off.x+0.5*self.m2_width, bm_off.y+0.5*contact.m2m3.width))
    
                    if (self.ibank_orien == "H"): 
                        pin = self.inbank_inst[k].get_pin("dout[{0}]".format(i)).ll()
                        yoff = self.dout1_off.y+ i*self.pitch +  0.5*self.m1_width
                        dout_off = vector(pin.x,  yoff)
                        dout_height =  pin.y -  yoff + self.m1_width
                        self.add_rect(layer="m2", 
                                      offset=dout_off, 
                                      width=self.m2_width, 
                                      height=dout_height)
                        self.add_via(self.m1_stack, (dout_off.x, dout_off.y-self.via_yshift))

                    else: 
                        
                        dout_off0 = self.inbank_inst[0].get_pin("dout[{0}]".format(i))
                        dout_off1 = self.inbank_inst[1].get_pin("dout[{0}]".format(i))
                        dout_off2 = self.inbank_inst[3].get_pin("dout[{0}]".format(i))
                        dout_off1_y = self.dout1_off.y+ i*self.pitch +self.m1_width
                        dout_off2_y = self.dout2_off.y+ i*self.pitch
                        dout_off3 = self.inbank_inst[2].get_pin("dout[{0}]".format(i))
                        self.add_wire(self.m1_stack, [(dout_off0.uc().x,dout_off0.ll().y),
                                      (dout_off0.uc().x,dout_off1_y),(dout_off1.uc().x,dout_off1_y)], widen_short_wires=False)

                        x_off = self.inbank_inst[1].lr().x+(i+1)*self.pitch
                        self.add_wire(self.m1_stack,[(dout_off1.uc().x,dout_off1.ll().y),
                                      (dout_off1.uc().x,dout_off1_y),
                                      (x_off,dout_off1_y), (x_off,dout_off2_y),
                                      (dout_off2.uc().x,dout_off2_y),
                                      (dout_off2.uc().x,dout_off2.ll().y)], widen_short_wires=False) 
                        self.add_wire(self.m1_stack, [(dout_off2.uc().x,dout_off2_y),
                                      (dout_off3.uc().x,dout_off2_y),
                                      (dout_off3.uc().x,dout_off3.ll().y)], widen_short_wires=False) 

        if (self.num_obank == 4 and self.obank_orien == "V"):
            din_bus = [self.din1_off.y, self.din2_off.y]
            dout_bus = [self.dout1_off.y, self.dout2_off.y]
            for k in range(self.num_obank//2):
                for j in range(2):
                    for i in range(self.w_size):
                        pin1 = self.inbank_inst[k+2*j].get_pin("din[{0}]".format(i)).ll()
                        yoff1 = din_bus[j]+ i*self.pitch + 0.5*self.m1_width
                        din_off1 = vector(pin1.x, yoff1)
                        din1_height =  pin1.y -  yoff1 + self.m1_width
                        self.add_rect(layer="m2", 
                                      offset=din_off1, 
                                      width=self.m2_width, 
                                      height=din1_height)
                        self.add_via(self.m1_stack, (din_off1.x, din_off1.y-self.via_yshift))
    
                        if self.mask:
                            pin1 = self.inbank_inst[k+2*j].get_pin("bm[{0}]".format(i)).ll()
                            bm_off1 = vector(pin1.x,  yoff1)
                            bm1_height =  pin1.y -  yoff1 + self.m1_width
                            self.add_rect(layer="m2", 
                                      offset=bm_off1, 
                                      width=self.m2_width, 
                                      height=bm1_height)
                            self.add_via_center(self.m2_stack, (bm_off1.x+0.5*self.m2_width, bm_off1.y+0.5*contact.m2m3.width))
                
                    if (self.ibank_orien == "H"):
                        for i in range(self.w_size): 
                            pin1 = self.inbank_inst[k+2*j].get_pin("dout[{0}]".format(i)).ll()
                            yoff1 = dout_bus[j]+ i*self.pitch +  0.5*self.m1_width
                            dout_off1 = vector(pin1.x, yoff1)
                            dout1_height =  pin1.y - yoff1 + self.m1_width
                            self.add_rect(layer="m2", 
                                          offset=dout_off1, 
                                          width=self.m2_width, 
                                          height=dout1_height)
                            self.add_via(self.m1_stack, (dout_off1.x, dout_off1.y-self.via_yshift))

                            xoff1 = self.inbank_inst[1].lr().x
                            xoff2 = xoff1+(i+3)*self.pitch
                            yoff1 = dout_bus[0]+ i*self.pitch + self.m1_width
                            yoff2 = dout_bus[1]+ i*self.pitch + self.m1_width
                            self.add_wire(self.m1_stack, [(xoff1, yoff1), (xoff2, yoff1), (xoff2, yoff2), (xoff1, yoff2)], widen_short_wires=False)
                    
                            xoff2 = xoff1+(i+self.w_size+3)*self.pitch
                            yoff1 = din_bus[0]+ i*self.pitch
                            yoff2 = din_bus[1]+ i*self.pitch
                            self.add_wire(self.m1_stack, [(xoff1, yoff1+ self.m1_width), (xoff2, yoff1+ self.m1_width), 
                                                          (xoff2, yoff2+ self.m1_width), (xoff1, yoff2+ self.m1_width)], widen_short_wires=False)
                        
                            if self.mask:
                                xoff2 = self.inbank_inst[1].lr().x+(i+2*self.w_size+3)*self.pitch
                                self.add_path("m3", [(xoff1, yoff1+ self.m3_width), (xoff2, yoff1+ self.m3_width)])
                                self.add_path("m3", [(xoff2, yoff2+ self.m3_width), (xoff1, yoff2+ self.m3_width)])
                                self.add_path("m2", [(xoff2, yoff1+ self.m3_width), (xoff2, yoff2+ self.m3_width)])
                                self.add_via_center(self.m2_stack, (xoff2, yoff1+ self.m3_width))
                                self.add_via_center(self.m2_stack, (xoff2, yoff2+ self.m3_width))

                    else: 
                        for i in range(self.w_size):
                            dout_off0 = self.inbank_inst[0].get_pin("dout[{0}]".format(i))
                            dout_off1 = self.inbank_inst[1].get_pin("dout[{0}]".format(i))
                            dout_off2 = self.inbank_inst[2].get_pin("dout[{0}]".format(i))
                            dout_off3 = self.inbank_inst[3].get_pin("dout[{0}]".format(i))
                        
                            dout_off1_y = self.dout1_off.y+ i*self.pitch +self.m1_width
                            dout_off2_y = self.dout2_off.y+ i*self.pitch +self.m1_width
                            dout_off3_y = self.dout_bus3_off.y+ i*self.pitch 

                            x_off = self.inbank_inst[1].lr().x+(i+3)*self.pitch
                            self.add_wire(self.m1_stack,[(dout_off0.uc().x,dout_off0.ll().y),
                                      (dout_off0.uc().x,dout_off1_y),
                                      (x_off,dout_off1_y), (x_off,dout_off3_y),
                                      (dout_off1.uc().x,dout_off3_y),
                                      (dout_off1.uc().x,dout_off1.ll().y)], widen_short_wires=False) 
                        
                            self.add_wire(self.m1_stack, [(dout_off3.uc().x,dout_off3.ll().y),
                                      (dout_off3.uc().x,dout_off2_y),
                                      (x_off,dout_off2_y), (x_off,dout_off3_y),
                                      (dout_off2.uc().x,dout_off3_y),
                                      (dout_off2.uc().x,dout_off2.ll().y)], widen_short_wires=False) 

                            xoff1 = self.inbank_inst[1].lr().x
                            xoff2 = self.inbank_inst[1].lr().x+(i+self.w_size+3)*self.pitch
                            yoff1 = din_bus[0]+ i*self.pitch
                            yoff2 = din_bus[1]+ i*self.pitch
                            self.add_wire(self.m1_stack, [(xoff1, yoff1+ self.m1_width), (xoff2, yoff1+ self.m1_width), 
                                                           (xoff2, yoff2+ self.m1_width), (xoff1, yoff2+ self.m1_width)], widen_short_wires=False)

                            if self.mask:
                                xoff2 = self.inbank_inst[1].lr().x+(i+2*self.w_size+3)*self.pitch
                                self.add_path("m3", [(xoff1, yoff1+ self.m3_width), (xoff2, yoff1+ self.m3_width)])
                                self.add_path("m3", [(xoff2, yoff2+ self.m3_width), (xoff1, yoff2+ self.m3_width)])
                                self.add_path("m2", [(xoff2, yoff1+ self.m3_width),(xoff2, yoff2+ self.m3_width)])
                                self.add_via_center(self.m2_stack, (xoff2, yoff1+ self.m3_width))
                                self.add_via_center(self.m2_stack, (xoff2, yoff2+ self.m3_width))

        if (self.num_obank == 2 or self.obank_orien == "H"):
            # Addr Connections
            for k in range(self.num_obank):
                for i in range(self.inbank_addr_size):
                    pin = self.inbank_inst[k].get_pin("addr[{0}]".format(i)).ll()
                    off = vector(pin.x, self.addr_bus_off.y+ i*self.pitch+ 0.5*self.m1_width) 
                    height =  pin.y - self.addr_bus_off.y - i*self.pitch
                    self.add_rect(layer="m2", 
                                  offset=off, 
                                  width=self.m2_width, 
                                  height=height)
                    self.add_via(self.m1_stack, (off.x, off.y-self.via_yshift))
        
            # sel Connections
            for k in range(self.num_obank):
               yoff = self.H_ctrl_bus_pos["sel[{0}]".format(k)].cy()
               pin = self.inbank_inst[k].get_pin("S").ll()
               sel_off = vector(pin.x, yoff - 0.5*self.m1_width)
               sel_heigh =  pin.y - yoff + self.m1_width
               self.add_rect(layer="m2", 
                             offset=sel_off, 
                             width=self.m2_width, 
                             height=sel_heigh)
               self.add_via(self.m1_stack, (sel_off.x+self.m2_width, sel_off.y), rotate=90)
               self.add_via(self.m1_stack, (sel_off.x,pin.y -self.via_yshift))
            
            if self.power_gate:
               for k in range(self.num_obank):
                   pos1=self.inbank_inst[k].get_pin("sleep")
                   yoff = self.H_ctrl_bus_pos["sleep"].cy()
                   if k%2:
                       xoff=pos1.lx()-2*self.pitch                  
                   else:
                       xoff=pos1.rx()+2*self.pitch              
                   pos2 = vector(xoff,pos1.lc().y)
                   pos3 = vector(pos2.x, yoff- 0.5*self.m1_width)
                   sleep_heigh =  self.inbank_inst[k].get_pin("sleep").lc().y - yoff
            
                   self.add_wire(self.m1_stack, [pos1.lc(), pos2, pos3], widen_short_wires=False)
                   self.add_via_center(self.m1_stack, pos3, rotate=90)
            
            # control signal Connections
            for k in range(self.num_obank):
                # Connect the split nodes in split_list to nodes in split_ctrl_list (keep the order)
                split_list = ["wack", "wreq",  "rreq", "rack", "ack", "rw",  "w", "r",
                              "ack_merge", "rw_en1_S", "rw_en2_S", "Mack_S", "Mrack_S", "Mwack_S", "Mdout"]
                split_ctrl_list = ["pre_wack", "wreq",  "rreq", "pre_rack", "pre_ack", "rw",  "w",
                                   "r", "ack{0}".format(k), "ack_b{0}".format(k), "ack_b", 
                                   "rw_merge", "rreq", "wreq", "rack"]
                for i in range(len(split_list)):
                    yoff = self.H_ctrl_bus_pos[split_ctrl_list[i]].cy()
                    pin = self.inbank_inst[k].get_pin(split_list[i]).ll()
                    split_off = vector(pin.x, yoff- 0.5*self.m1_width)
                    split_heigh =  pin.y - yoff + 0.5*self.m1_width
                    self.add_rect(layer="m2", 
                                  offset=split_off, 
                                  width=self.m2_width, 
                                  height=split_heigh)
                    self.add_via(self.m1_stack, (split_off.x, split_off.y-self.via_yshift))
        
            # vdd and gnd Connections
            power_pin=["vdd", "gnd"]
            for i in range(2):
                yoff = self.pow1_off.y+i*self.pow_pitch
                for k in range(self.num_obank):
                    pow_pin = self.inbank_inst[k].get_pin(power_pin[i])
                    
                    if pow_pin.by()<self.pow1_off.y:
                        sign2 = -1
                    else:
                        sign2 = +1

                    if (k%2 or self.obank_orien == "V"):
                        pow_off = vector(pow_pin.ll().x-(i+5)*self.pitch-i*self.pow_pitch,yoff)
                        if self.ibank_orien == "H":
                            pow_off = pow_off -vector(self.w_size*self.pitch, 0)
                        sign = -1

                    else:
                        pow_off = vector(pow_pin.lr().x+(i+self.w_size)*self.pitch+(i+1)*self.pow_pitch,yoff)
                        sign = 1

                    self.add_path("m2", [pow_off,(pow_off.x,pow_pin.lc().y+sign2*0.5*self.pow_width)], width =self.pow_width)
                    pos1=(pow_off.x+sign*0.5*self.pow_width, pow_pin.lc().y)
                    pos2=(pow_pin.lr().x, pow_pin.lc().y)
                    self.add_path("m3", [pos1, pos2], width =self.pow_width)
                    self.add_via_center(self.m2_stack, (pow_off.x, pow_off.y+0.5*self.pow_width), size=[self.num_via, self.num_via])
                    self.add_via_center(self.m2_stack, (pow_off.x, pow_pin.lc().y), size=[self.num_via, self.num_via])
            
            for k in range(self.num_obank):
                pin = self.inbank_inst[k].get_pin("reset")
                if (k%2 or self.obank_orien == "V") :
                    xoff = pin.ll().x-self.pitch
                else:
                    xoff = pin.lr().x+self.pitch

                off = vector(xoff, self.reset1_off.y + 0.5*self.m1_width)
                self.add_wire(self.m1_stack, [off,(off.x,pin.lc().y), (pin.lr().x,pin.lc().y)], widen_short_wires=False)
                self.add_via(self.m1_stack, (off.x-0.5*self.m1_width, off.y-self.via_yshift))

            # split_merge_control_inst Connections
            ctrl_pin_list = ["wack", "wreq",  "rreq", "rack", "ack", "rw",  "w", "r", 
                             "ack_b", "rw_merge", "pre_ack", "pre_wack", "pre_rack"]
            for k in range(self.num_obank):
                ctrl_pin_list.extend(["ack{0}".format(k), "ack_b{0}".format(k)])
            for i in range(len(ctrl_pin_list)):
                pin = self.out_sm_ctrl_inst.get_pin(ctrl_pin_list[i]).ll()
                yoff = self.H_ctrl_bus_pos[ctrl_pin_list[i]].cy()
                ctrl_off = vector(pin.x, yoff - 0.5*self.m1_width)
                ctrl_heigh =  pin.y - yoff + 0.5*self.m1_width
                self.add_rect(layer="m2", 
                              offset=ctrl_off, 
                              width=self.m2_width, 
                              height=ctrl_heigh)
                self.add_via(self.m1_stack, (ctrl_off.x, ctrl_off.y-self.via_yshift))        
            
            power_pin =["vdd", "gnd"]
            for i in range(2):
                yoff = self.pow1_off.y + i*self.pow_pitch + 0.5*self.m1_width
                pin = self.out_sm_ctrl_inst.get_pin(power_pin[i]).ll()
                pow_off = vector(pin.x, yoff)
                pow_heigh =  pin.y - yoff +self.m1_width
                self.add_rect(layer="m2", 
                          offset=pow_off, 
                          width=self.m2_width, 
                          height=pow_heigh)
                self.add_via_center(self.m2_stack, (pow_off.x+0.5*self.m2_width, pow_off.y+0.5*self.pow_width), size=[1, self.num_via])        

            if self.num_obank == 2:
                addr_pin = ["addr[0]","sel[0]", "sel[1]"]
            if self.num_obank == 4:
                addr_pin = ["addr[0]","addr[1]", 
                        "sel[0]", "sel[1]", "sel[2]", "sel[3]"]
            for i in range(len(addr_pin)):
                pin = self.out_sm_ctrl_inst.get_pin(addr_pin[i]).ll()
                yoff = self.addr_bus_off.y + (i+self.inbank_addr_size)*self.pitch + 0.5*self.m1_width
                addr_off = vector(pin.x, yoff)
                addr_heigh =  pin.y - yoff + self.m1_width
                self.add_rect(layer="m2", 
                              offset=addr_off, 
                              width=self.m2_width, 
                              height=addr_heigh)
                self.add_via(self.m1_stack, (addr_off.x,addr_off.y-self.via_yshift))        

        if (self.num_obank == 4 and self.obank_orien == "V"):
            # Addr Connections
            bus = [self.addr_bus_off, self.addr_bus2_off]
            for k in range(self.num_obank//2):
                for j in range(2):
                    for i in range(self.inbank_addr_size):
                        pin = self.inbank_inst[k+2*j].get_pin("addr[{0}]".format(i)).ll()
                        off = vector(pin.x, bus[j].y+ i*self.pitch+  0.5*self.m1_width) 
                        height = pin.y -  bus[j].y - i*self.pitch

                        self.add_rect(layer="m2", 
                                  offset=off, 
                                  width=self.m2_width, 
                                  height=height)
                        self.add_via(self.m1_stack, (off.x, off.y-self.via_yshift))
                    
                        x_off = self.inbank_inst[1].lr().x+(i+2*self.w_size+3)*self.pitch
                        if self.mask:
                            x_off = self.inbank_inst[1].lr().x+(i+3*self.w_size+3)*self.pitch
                        addr1_off = self.addr_bus_off.y+ i*self.pitch +self.m1_width
                        addr2_off = self.addr_bus2_off.y+ i*self.pitch +self.m1_width
                        self.add_wire(self.m1_stack, 
                                  [(self.inbank_inst[1].rx(), addr1_off),
                                  (x_off, addr1_off), (x_off, addr2_off),
                                  (self.inbank_inst[1].rx(), addr2_off)], widen_short_wires=False)
                    
            # sel Connections
            bus= [self.H_ctrl_bus_pos, self.H2_ctrl_bus_pos]
            for k in range(self.num_obank//2):
                for i in range(2):
                    pin = self.inbank_inst[k+2*i].get_pin("S").ll()
                    if k%2:
                        off = vector(pin.x, bus[i]["sel[{0}]".format(k+2*i)].cy()-0.5*self.m1_width)
                    else:
                        off = vector(pin.x, bus[i]["sel[{0}]".format(k+2*i)].cy()-self.m1_width)
                    heigh =  pin.y - off.y
                    self.add_rect(layer="m2", 
                              offset=off, 
                              width=self.m2_width, 
                              height=heigh)
                    self.add_via(self.m1_stack, (off.x, off.y-self.via_yshift))
                    self.add_via(self.m1_stack, (off.x, pin.y-self.via_yshift ))

            # control signal Connections
            for k in range(self.num_obank//2):
                # Connect the split nodes in split_list to nodes in split_ctrl_list (kepp the order)
                split_list = ["wack", "wreq",  "rreq", "rack", "ack", "rw",  "w", "r",
                              "ack_merge", "rw_en1_S", "rw_en2_S", "Mack_S", "Mrack_S", "Mwack_S", "Mdout"]
                
                ctrl_list ={}
                for j in range(2):
                    ctrl_list[j] = ["pre_wack", "wreq",  "rreq", "pre_rack", "pre_ack", "rw",  "w", 
                                    "r", "ack{0}".format(k+2*j), "ack_b{0}".format(k+2*j), "ack_b", 
                                    "rw_merge", "rreq", "wreq", "rack"]
                
                for i in range(len(split_list)):
                    for j in range(2):
                        pin = self.inbank_inst[k+2*j].get_pin(split_list[i]).ll()
                        off = vector(pin.x, bus[j][ctrl_list[j][i]].y-  0.5*self.m1_width)
                        heigh =  pin.y - bus[j][ctrl_list[j][i]].y + 0.5*self.m1_width
                        self.add_rect(layer="m2", 
                                      offset=off, 
                                      width=self.m2_width, 
                                      height=heigh)
                        self.add_via(self.m1_stack, (off.x, off.y-self.via_yshift))
        
            # vdd and gnd Connections
            pow_pins=["vdd", "gnd"]
            for k in range(self.num_obank//2):
                
                for m in range(len(self.inbank_inst[k].get_pins("vdd"))):
                    vdd1_pin = self.inbank_inst[k].get_pins("vdd")[m]
                    vdd1_off = vector(vdd1_pin.ll().x-4*self.pitch-self.pow_pitch, self.pow1_off.y+0.5*self.m1_width)
                
                    if vdd1_pin.lc().y < self.pow1_off.y:
                        sign = -0.5*self.pow_width
                    else:
                        sign = +0.5*self.pow_width
                
                    self.add_path("m2", [vdd1_off,(vdd1_off.x, vdd1_pin.lc().y+sign)], width =self.pow_width)
                    pos1=(vdd1_off.x-0.5*self.pow_width, vdd1_pin.lc().y)
                    pos2=(vdd1_pin.lr().x, vdd1_pin.lc().y)
                    self.add_path("m3", [pos1, pos2], width =self.pow_width)
                    self.add_via_center(self.m2_stack, (vdd1_off.x, vdd1_off.y+0.5*self.pow_width), size=[self.num_via, self.num_via])
                    self.add_via_center(self.m2_stack, (vdd1_off.x, vdd1_pin.lc().y), size=[self.num_via, self.num_via])
                
                    gnd1_pin = self.inbank_inst[k].get_pins("gnd")[m]
                    gnd1_off = vector(gnd1_pin.ll().x-5*self.pitch-2*self.pow_pitch, self.pow1_off.y+ self.pow_pitch+0.5*self.m1_width)
                    self.add_path("m2", [gnd1_off,(gnd1_off.x, gnd1_pin.lc().y+sign)], width =self.pow_width)
                    pos1=(gnd1_off.x-0.5*self.pow_width, gnd1_pin.lc().y)
                    pos2=(gnd1_pin.lr().x, gnd1_pin.lc().y)
                    self.add_path("m3", [pos1, pos2], width =self.pow_width)
                    self.add_via_center(self.m2_stack, (gnd1_off.x, gnd1_off.y+0.5*self.pow_width), size=[self.num_via, self.num_via])
                    self.add_via_center(self.m2_stack, (gnd1_off.x, gnd1_pin.lc().y), size=[self.num_via, self.num_via])
                
                reset1_pin = self.inbank_inst[k].get_pin("reset")
                reset1_off = vector(reset1_pin.ll().x-2*self.pitch, self.reset1_off.y + 0.5*self.m1_width)
                self.add_wire(self.m1_stack, [reset1_off,(reset1_off.x, reset1_pin.lc().y), (reset1_pin.lr().x, reset1_pin.lc().y)], widen_short_wires=False)
                self.add_via_center(self.m1_stack, (reset1_off.x, reset1_off.y))
                
                if self.power_gate:
                    sleep1_pin = self.inbank_inst[k].get_pin("sleep")
                    sleep1_off = vector(sleep1_pin.ll().x-3*self.pitch, self.sleep1_off.y + 0.5*self.m1_width)
                    self.add_wire(self.m1_stack, [sleep1_off,(sleep1_off.x, sleep1_pin.lc().y), (sleep1_pin.lr().x, sleep1_pin.lc().y)], widen_short_wires=False)
                    self.add_via_center(self.m1_stack, (sleep1_off.x, sleep1_off.y))

                
                for m in range(len(self.inbank_inst[k+2].get_pins("vdd"))):
                    vdd2_pin = self.inbank_inst[k+2].get_pins("vdd")[m]
                    vdd2_off = vector(vdd2_pin.ll().x-4*self.pitch-self.pow_pitch, self.pow2_off.y+0.5*self.m1_width)
                    if vdd2_pin.lc().y < self.pow2_off.y:
                        sign2 = -0.5*self.pow_width
                    else:
                        sign2 = +0.5*self.pow_width

                    self.add_path("m2", [vdd2_off,(vdd2_off.x, vdd2_pin.lc().y+sign2)], width =self.pow_width)
                    pos1=(vdd2_off.x-0.5*self.pow_width, vdd2_pin.lc().y)
                    pos2=(vdd2_pin.lr().x, vdd2_pin.lc().y)
                    self.add_path("m3", [pos1, pos2], width =self.pow_width)
                    self.add_via_center(self.m2_stack, (vdd2_off.x, vdd2_off.y+0.5*self.pow_width), size=[self.num_via, self.num_via])
                    self.add_via_center(self.m2_stack, (vdd2_off.x, vdd2_pin.lc().y), size=[self.num_via, self.num_via])
            
                    gnd2_pin = self.inbank_inst[k+2].get_pins("gnd")[m]
                    gnd2_off = vector(gnd2_pin.ll().x-5*self.pitch-2*self.pow_pitch, self.pow2_off.y+ self.pow_pitch+0.5*self.m1_width)
                    self.add_path("m2", [gnd2_off,(gnd2_off.x, gnd2_pin.lc().y+sign2)], width =self.pow_width)
                    pos1=(gnd2_off.x-0.5*self.pow_width, gnd2_pin.lc().y)
                    pos2=(gnd2_pin.lr().x, gnd2_pin.lc().y)
                    self.add_path("m3", [pos1, pos2], width =self.pow_width)
                    self.add_via_center(self.m2_stack, (gnd2_off.x, gnd2_off.y+0.5*self.pow_width), size=[self.num_via, self.num_via])
                    self.add_via_center(self.m2_stack, (gnd2_off.x, gnd2_pin.lc().y), size=[self.num_via, self.num_via])
                
                reset2_pin = self.inbank_inst[k+2].get_pin("reset")
                reset2_off = vector(reset2_pin.ll().x-2*self.pitch, self.reset2_off.y + 0.5*self.m1_width)
                self.add_wire(self.m1_stack, [reset2_off,(reset2_off.x, reset2_pin.lc().y), (reset2_pin.lr().x, reset2_pin.lc().y)], widen_short_wires=False)
                self.add_via_center(self.m1_stack, (reset2_off.x, reset2_off.y))
                if self.power_gate:
                    sleep2_pin = self.inbank_inst[k+2].get_pin("sleep")
                    sleep2_off = vector(sleep2_pin.ll().x-3*self.pitch, self.sleep2_off.y + 0.5*self.m1_width)
                    self.add_wire(self.m1_stack, [sleep2_off,(sleep2_off.x, sleep2_pin.lc().y), (sleep2_pin.lr().x, sleep2_pin.lc().y)], widen_short_wires=False)
                    self.add_via_center(self.m1_stack, (sleep2_off.x, sleep2_off.y))

            shift = 2*self.w_size
            if self.mask:
                shift = 3*self.w_size

            reset_xoff = self.inbank_inst[1].lr().x+ (self.inbank_addr_size+shift+3)*self.pitch
            self.add_wire(self.m1_stack, 
                          [(self.inbank_inst[1].lr().x, self.reset1_off.y+self.m1_width),
                          (reset_xoff, self.reset1_off.y+self.m1_width),
                          (reset_xoff, self.reset2_off.y+self.m1_width),
                          (self.inbank_inst[1].lr().x, self.reset2_off.y+self.m1_width)], widen_short_wires=False)

            if self.power_gate:
                sleep_xoff = self.inbank_inst[1].lr().x+ (self.inbank_addr_size+shift+4)*self.pitch
                self.add_wire(self.m1_stack, 
                              [(self.inbank_inst[1].lr().x, self.sleep1_off.y+self.m1_width),
                              (sleep_xoff, self.sleep1_off.y+self.m1_width),
                              (sleep_xoff, self.sleep2_off.y+self.m1_width),
                              (self.inbank_inst[1].lr().x, self.sleep2_off.y+self.m1_width)], widen_short_wires=False)
            
            # split_merge_control_inst Connections
            ctrl_pin_list = ["wack", "wreq",  "rreq", "rack", "ack", "rw",  "w", "r", 
                            "ack_b", "rw_merge", "pre_ack", "pre_wack", "pre_rack"]
            
            for k in range(self.num_obank):
                ctrl_pin_list.extend(["ack{0}".format(k), "ack_b{0}".format(k)])
            for i in range(len(ctrl_pin_list)):
                pin = self.out_sm_ctrl_inst.get_pin(ctrl_pin_list[i]).ll()
                yoff = self.H_ctrl_bus_pos[ctrl_pin_list[i]].cy()
                ctrl_off = vector(pin.x, yoff- 0.5*self.m1_width)
                ctrl2_off = vector(ctrl_off.x, self.H2_ctrl_bus_pos[ctrl_pin_list[i]].cy()- 0.5*self.m1_width)
                ctrl_heigh =  pin.y -  yoff + 0.5*self.m1_width

                self.add_rect(layer="m2", 
                              offset=ctrl_off, 
                              width=self.m2_width, 
                              height=ctrl_heigh)
                self.add_via(self.m1_stack, (ctrl_off.x, ctrl_off.y-self.via_yshift))
                self.add_via(self.m1_stack, (ctrl2_off.x, ctrl2_off.y-self.via_yshift))        
            
            power_pin =["vdd", "gnd"]
            for i in range(2):
                pin = self.out_sm_ctrl_inst.get_pin(power_pin[i]).ll()
                pow_off = vector(pin.x, self.pow1_off.y + i*self.pow_pitch + 0.5*self.m1_width)
                pow2_off = vector(pow_off.x, self.pow2_off.y + i*self.pow_pitch + 0.5*self.m1_width)
                pow_heigh =  pin.y- pow_off.y + self.m1_width

                self.add_rect(layer="m2", 
                              offset=pow_off, 
                              width=self.m2_width, 
                              height=pow_heigh)
                self.add_via(self.m2_stack, (pow_off.x, pow_off.y-self.via_yshift), size=[1, self.num_via])
                self.add_via(self.m2_stack, (pow2_off.x, pow2_off.y-self.via_yshift), size=[1, self.num_via])                

            if self.num_obank == 2:
                addr_pin = ["addr[0]","sel[0]", "sel[1]"]
            if self.num_obank == 4:
                addr_pin = ["addr[0]","addr[1]", "sel[0]", "sel[1]", "sel[2]", "sel[3]"]
            for i in range(len(addr_pin)):
                shift = (i+self.inbank_addr_size)*self.pitch + 0.5*self.m1_width
                pin = self.out_sm_ctrl_inst.get_pin(addr_pin[i]).ll()
                addr_off = vector(pin.x, self.addr_bus_off.y + shift)
                addr2_off = vector(addr_off.x, self.addr_bus2_off.y + shift)
                addr_heigh =  pin.y -  self.addr_bus_off.y - shift + self.m1_width
                self.add_rect(layer="m2", 
                              offset=addr_off, 
                              width=self.m2_width, 
                              height=addr_heigh)
                self.add_via(self.m1_stack, (addr_off.x, addr_off.y-self.via_yshift))
                self.add_via(self.m1_stack, (addr2_off.x, addr2_off.y-self.via_yshift))        

        # select= vdd Connection
        sel_pos1=self.out_sm_ctrl_inst.get_pin("S").uc()
        sel_pos2=self.out_sm_ctrl_inst.get_pin("vdd").uc()
        pos1=vector(sel_pos1.x, sel_pos1.y-2*self.pitch)
        pos2=vector(sel_pos2.x, pos1.y)
        self.add_wire(self.m1_stack, [sel_pos1, pos1, pos2, sel_pos2], widen_short_wires=False)
    
    def sp_write(self, sp_name):
        """ Write the entire spice of the object to the file """
        sp = open(sp_name, 'w')

        sp.write("**************************************************\n")
        sp.write("* AMC generated memory.\n")
        sp.write("* Number of Words: {}\n".format(self.total_bits//self.w_size))
        sp.write("* Word Size: {}\n".format(self.w_size))
        sp.write("* Number of Banks: {}\n".format(self.num_ibank*self.num_obank))
        sp.write("**************************************************\n")        
        usedMODS = list()
        self.sp_write_file(sp, usedMODS)
        del usedMODS
        sp.close()

    def save_output(self):
        """ Save all the output files while reporting time to do it as well. """

        # Save the standar spice file
        start_time = datetime.datetime.now()
        spname = OPTS.output_path + self.name + ".sp"
        print("\n SP: Writing to {0}".format(spname))
        self.sp_write(spname)
        print_time("Spice writing", datetime.datetime.now(), start_time)

        # Save the extracted spice file if requested
        if OPTS.use_pex:
            start_time = datetime.datetime.now()
            sp_file = OPTS.output_path + "temp_pex.sp"
            calibre.run_pex(self.name, gdsname, spname, output=sp_file)
            print_time("Extraction", datetime.datetime.now(), start_time)
        else:
            # Use generated spice file for characterization
            sp_file = spname
        
        # Write the layout
        start_time = datetime.datetime.now()
        gdsname = OPTS.output_path + self.name + ".gds"
        print("\n GDS: Writing to {0}".format(gdsname))
        self.gds_write(gdsname)
        print_time("GDS", datetime.datetime.now(), start_time)

        # Create a LEF physical model
        start_time = datetime.datetime.now()
        lefname = OPTS.output_path + self.name + ".lef"
        print("\n LEF: Writing to {0}".format(lefname))
        self.lef_write(lefname)
        print_time("LEF", datetime.datetime.now(), start_time)

        # Write a verilog model
        start_time = datetime.datetime.now()
        vname = OPTS.output_path + self.name + ".v"
        print("\n Verilog: Writing to {0}".format(vname))
        self.verilog_write(vname)
        print_time("Verilog", datetime.datetime.now(), start_time)
        
        # Characterize the design
        if OPTS.characterize:
            start_time = datetime.datetime.now()        
            from characterizer import lib
            print("\n LIB: Characterizing... ")
            if OPTS.spice_name!="":
                print("Performing simulation-based characterization with {}".format(OPTS.spice_name))
            if OPTS.trim_netlist:
                print("Trimming netlist to speed up characterization.")
            lib.lib(out_dir=OPTS.output_path, sram=self)
            print_time("Characterization", datetime.datetime.now(), start_time)
