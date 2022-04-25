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
import getpass
import design
import debug
import contact
from math import log
from vector import vector
from tech import info, drc
from bank import bank
from split_array import split_array
from merge_array import merge_array
from split_merge_control import split_merge_control

class multi_bank(design.design):
    """ Dynamically generated multi bank (1, 2 or 4) asynchronous SRAM with split and merge arrays"""

    def __init__(self, word_size, words_per_row, num_rows, num_subanks, num_banks,  
                 orientation, two_level_bank, mask, power_gate, name):
        design.design.__init__(self, name)

        self.w_size= word_size
        self.w_per_row= words_per_row
        self.num_rows= num_rows
        self.num_subanks= num_subanks
        self.num_banks= num_banks
        
        # banks can be stacked or placed in an horizontal direction (set to "H" or "V")
        self.orien= orientation

        # If two_level_bank, second level of split and merge cells will be added
        self.two_level_bank= two_level_bank
        
        self.mask = mask
        self.power_gate = power_gate 
        
        self.compute_sizes()
        self.add_pins()
        self.create_layout()
        self.offset_all_coordinates()

    def compute_sizes(self):
        """ Compute the address sizes """
        
        self.row_addr_size= int(log(self.num_rows, 2))
        self.col_addr_size= int(log(self.num_subanks, 2))
        self.column_mux_addr_size= int(log(self.w_per_row, 2))
        self.bank_addr_size= self.col_addr_size + self.row_addr_size + self.column_mux_addr_size
        self.addr_size= self.bank_addr_size + int(log(self.num_banks, 2))
        
    def add_pins(self):
        """ Add pins for multi-bank, order of the pins is important """

        for i in range(self.w_size):
            self.add_pin("din[{0}]".format(i))
        for i in range(self.w_size):
            self.add_pin("dout[{0}]".format(i))
        for i in range(self.addr_size):
            self.add_pin("addr[{0}]".format(i))
        if self.mask:
            for i in range(self.w_size):
                self.add_pin("bm[{0}]".format(i))
        self.add_pin_list(["reset","r","w","rw","ack","rack","rreq","wreq","wack"])
        if (self.num_banks > 1 and self.two_level_bank):
            self.add_pin_list(["S","ack_merge","rw_en1_S","rw_en2_S","Mack_S","Mrack_S", "Mwack_S", "Mdout"])
        if self.power_gate:
            self.add_pin("sleep")

        self.add_pin_list(["vdd", "gnd"])

    def create_layout(self):
        """ Layout creation """
        
        self.create_modules()
        
        self.pow_width = self.bank.pow_width
        self.pow_pitch = self.bank.pow_pitch
        self.pitch = max(self.m_pitch("m1"), self.m_pitch("m2"))
        self.num_via = self.bank.num_via

        if self.num_banks == 1:
            self.pow_via_shift = vector(0.5*self.pow_width, 0.5*contact.m1m2.height)
            self.add_single_bank_modules()
        elif self.num_banks == 2:
            self.pow_via_shift = vector(0.5*self.pow_width, 0.5*self.pow_width)
            self.add_two_bank_modules()
            if self.two_level_bank:
                self.create_split_merge()
        elif self.num_banks == 4:
            self.pow_via_shift = vector(0.5*self.pow_width, 0.5*self.pow_width)
            self.add_four_bank_modules()
            if self.two_level_bank:
                self.create_split_merge()
        else:
            debug.error("Invalid number of banks! only 1, 2 and 4 banks are allowed :)",-1)

    def create_split_merge(self):
        """ Create and routes the outter (second-level) split and merge modules """

        self.add_split_merge_cells()
        self.route_data_split_merge()
        self.route_addr_ctrl_split_merge()
        self.route_split_cells_powers_and_selects()

    def create_modules(self):
        """ Create all the modules that will be used """

        # Create the bank module (up to four are instantiated)
        # With only one bank, there is no split and merge, hence, two_level is off
        if self.num_banks ==1:
            two_level_bank=False  
        else:
            two_level_bank=True
        self.bank= bank(word_size=self.w_size, words_per_row=self.w_per_row,
                        num_rows=self.num_rows, num_subanks=self.num_subanks, 
                        two_level_bank=two_level_bank, mask=self.mask, power_gate=self.power_gate, name="bank")
        self.add_mod(self.bank)

        if self.num_banks >1:
            self.sp_mrg_ctrl= split_merge_control(num_banks=self.num_banks)
            self.add_mod(self.sp_mrg_ctrl)

        if self.two_level_bank:
            self.dsplit_ary= split_array(name="outter_data_split_array", 
                                         word_size=self.w_size, 
                                         words_per_row=self.w_per_row,
                                         mask = self.mask)
            self.add_mod(self.dsplit_ary)

            self.dmerge_ary= merge_array(name="outter_data_merge_array", 
                                         word_size=self.w_size, 
                                         words_per_row=self.w_per_row)
            self.add_mod(self.dmerge_ary)
        
            self.addr_split_ary= split_array(name="outter_addr_split_array", 
                                             word_size=self.addr_size, 
                                             words_per_row=1,
                                             mask= False)
            self.add_mod(self.addr_split_ary)

            # 5: R, W, RW, WREQ, RREQ
            self.ctrl_split_ary= split_array(name="outter_ctrl_split_array", 
                                             word_size=5, 
                                             words_per_row=1,
                                             mask= False)
            self.add_mod(self.ctrl_split_ary)


            self.ctrl_mrg_cell= merge_array(name="outter_ctrl_merge_cell", 
                                            word_size=1, 
                                            words_per_row=1)
            self.add_mod(self.ctrl_mrg_cell)


    def add_bank(self, bank_num, position, x_flip, y_flip):
        """ Place a bank at the given position with orientations """

        # x_flip ==  1 --> no flip in x_axis
        # x_flip == -1 --> flip in x_axis
        # y_flip ==  1 --> no flip in y_axis
        # y_flip == -1 --> flip in y_axis

        # x_flip and y_flip are used for position translation

        if x_flip == -1 and y_flip == -1:
            bank_rotation= 180
        else:
            bank_rotation= 0

        if x_flip == y_flip:
            bank_mirror= "R0"
        elif x_flip == -1:
            bank_mirror= "MX"
        elif y_flip == -1:
            bank_mirror= "MY"
        else:
            bank_mirror= "R0"
            
        bank_inst=self.add_inst(name="bank{0}".format(bank_num),
                                mod=self.bank,
                                offset=position,
                                mirror=bank_mirror,
                                rotate=bank_rotation)
        temp= []
        if (self.num_banks > 1 and self.two_level_bank):
            for i in range(self.num_subanks):
                for j in range(self.w_size):
                    temp.append("din_split[{0}]".format(j))
            for i in range(self.num_subanks):
                for j in range(self.w_size):
                    temp.append("dout_merge[{0}]".format(j))
            for i in range(self.bank_addr_size):
                temp.append("addr_split[{0}]".format(i))
            if self.mask:
                for i in range(self.num_subanks):
                    for j in range(self.w_size):
                        temp.append("bm_split[{0}]".format(j))

        else:
            for i in range(self.num_subanks):
                for j in range(self.w_size):
                    temp.append("din[{0}]".format(j))
            for i in range(self.num_subanks):
                for j in range(self.w_size):
                    temp.append("dout[{0}]".format(j))
            for i in range(self.bank_addr_size):
                temp.append("addr[{0}]".format(i))
            if self.mask:
                for i in range(self.num_subanks):
                    for j in range(self.w_size):
                        temp.append("bm[{0}]".format(j))
        
        if self.num_banks ==1:
            temp.extend(["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"])
        
        if (self.num_banks > 1 and not self.two_level_bank):
            temp.extend(["reset", "r", "w", "rw", "pre_ack", "pre_rack", "rreq", "wreq", "pre_wack"])
            temp.extend(["sel[{0}]".format(bank_num), "ack{0}".format(bank_num)]) 
            temp.extend(["ack_b{0}".format(bank_num), "ack_b", "rw_merge", "rreq", "wreq", "rack"])
        
        if (self.num_banks > 1 and self.two_level_bank):
            temp.extend(["reset", "r_split", "w_split", "rw_split", "pre_ack", "pre_rack"])
            temp.extend(["rreq_split", "wreq_split", "pre_wack", "sel[{0}]".format(bank_num)])
            temp.extend(["ack{0}".format(bank_num), "ack_b{0}".format(bank_num), "ack_b"])
            temp.extend(["rw_merge", "rreq_split", "wreq_split", "rack_merge"])
        
        if self.power_gate:
            temp.extend(["sleep"])

        temp.extend(["vdd", "gnd"])
        self.connect_inst(temp)
        return bank_inst
        

    def compute_bus_sizes(self):
        """ Compute the independent bus widths shared between two and four bank SRAMs """
        
        #8 : ("r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack")
        self.control_size= 8
        
        #5:("Mrack","rreq_b","Mwack","Mack","rw_merge") + "ack0:3_b", "wack0:3_b", "ack0:3", "wack0:3"
        self.merge_split_size= 5+ 2*self.num_banks
        
        # Vertical address + control + merge_split + one-hot bank select + reset+ vdd + gnd + S bus
        self.num_v_line= self.addr_size + self.control_size + self.merge_split_size+ self.num_banks+4
        if self.power_gate:
            self.num_v_line += 1
        self.v_bus_width= self.pitch*self.num_v_line
        self.bnk_to_bus_gap= 2*self.m3_width
        self.bnk_to_bnk_gap= 2*self.m3_width
        
        # Horizontal data bus size ( input and output data)
        self.num_h_line= self.w_size
        self.data_bus_height= self.pitch*self.num_h_line
        
        if self.orien == "H":
            self.data_bus_width= 2*(self.bank.width + self.bnk_to_bus_gap)+ self.sp_mrg_ctrl.height
        if self.orien == "V":
            self.data_bus_width= self.bank.width + self.bnk_to_bus_gap+ \
                                  max(self.sp_mrg_ctrl.height, 2*self.w_size*self.pitch)
            if self.num_banks == 4:
                if ((self.w_size+2)*self.pitch>self.sp_mrg_ctrl.height-self.v_bus_width) :
                    self.data_bus_width= self.data_bus_width+ (self.w_size+2)*self.pitch-\
                                         self.sp_mrg_ctrl.height+self.v_bus_width
        
        self.power_rail_width= self.data_bus_width

    def add_single_bank_modules(self):
        """ Adds a single bank SRAM """
        
        # No orientation or offset
        self.bank_inst= self.add_bank(0, [0, 0], 1, 1)
        self.add_single_bank_pins()
        self.width= self.bank.width
        self.height= self.bank.height+2*self.w_size*self.pitch+2*self.pow_pitch

    def add_two_bank_modules(self):
        """ Adds the moduels and the buses for a two bank SRAM. """
        
        self.compute_two_bank_offsets()
        self.add_two_banks()
        self.add_busses()
        self.route_banks()
    
    def add_four_bank_modules(self):
        """ Adds the modules and the buses for a four bank SRAM. """

        self.compute_four_bank_offsets()
        self.add_four_banks()
        self.add_busses()
        self.route_banks()
    
    def compute_two_bank_offsets(self):
        """ Compute the overall offsets for a two bank SRAM buses"""

        self.compute_bus_sizes()
        #Find the location of ack_merge which is the last pin in ctrl logic of bank
        self.bank_ack_mrg_off=self.bank.get_pin("ack_merge").by() + self.pitch
        if self.power_gate:
            self.bank_ack_mrg_off=self.bank.get_pin("sleep").by() + self.pitch
        
        if (self.sp_mrg_ctrl.height >= self.v_bus_width):
            v_off =abs(self.sp_mrg_ctrl.height-self.v_bus_width)

        else:
            v_off= 0

        if self.orien == "H":
            self.v_bus_height= self.bank_ack_mrg_off + self.bnk_to_bus_gap + \
                               2*(self.data_bus_height+self.pow_pitch)+self.pitch
            self.din1_bus_off= vector(0, 2*self.pow_pitch)
            self.v_bus_off= vector(self.bank.width+self.bnk_to_bus_gap+v_off, 0)
            self.pow_rail_1_off= vector(0, 0)
        
        if self.orien == "V":
            self.v_bus_height= self.bank_ack_mrg_off+self.bank.height+2*(self.bnk_to_bus_gap+ \
                               self.data_bus_height+self.pow_pitch + self.pitch)
            self.din1_bus_off= vector(-v_off, self.bank.height+self.bnk_to_bus_gap+ 2*self.pow_pitch)
            self.v_bus_off= vector(0,0)
            self.pow_rail_1_off= vector(-v_off, self.bank.height+self.bnk_to_bus_gap)

        if self.power_gate:
            self.sleep_off = self.v_bus_off
            self.reset_off= self.sleep_off + vector(self.pitch,0)
        else:
            self.reset_off= self.v_bus_off
        
        self.addr_bus1_off=  self.reset_off + vector(self.pitch,0)
        self.S_off= self.addr_bus1_off +vector(self.bank_addr_size*self.pitch,0)
        self.gnd_off= self.S_off +vector(self.pitch,0)
        self.vdd_off= self.gnd_off + vector(self.pitch,0)
        self.sel_bus_off= self.vdd_off + vector(self.pitch,0)
        self.addr_bus2_off= self.sel_bus_off + vector(self.num_banks*self.pitch,0)
        self.spl_mrg_ctrl_bus_off=  self.addr_bus2_off + vector(self.pitch,0)
        self.spl_mrg_in_off= self.spl_mrg_ctrl_bus_off + vector(5*self.pitch,0)
        self.ctrl_bus_off= self.spl_mrg_in_off + vector(2*self.pitch*self.num_banks,0)
        self.dout1_bus_off= vector(self.din1_bus_off.x,self.din1_bus_off.y + self.data_bus_height)

    def compute_four_bank_offsets(self):
        """ Compute the overall offsets for a four bank SRAM """
        
        self.compute_bus_sizes()
        #Find the location of ack_merge which is the last pin in ctrl logic of bank
        self.bank_ack_mrg_off=self.bank.get_pin("ack_merge").by() + self.pitch
        if self.power_gate:
            self.bank_ack_mrg_off=self.bank.get_pin("sleep").by() + self.pitch

        if (self.sp_mrg_ctrl.height >= self.v_bus_width):
            v_off =abs(self.sp_mrg_ctrl.height-self.v_bus_width)
        else:
            v_off= 0
        
        if self.orien == "H":
            self.v_bus_height= self.bank_ack_mrg_off+self.bank.height+2*(self.bnk_to_bus_gap +\
                               self.data_bus_height + self.pow_pitch + self.pitch) 
            self.pow_rail_1_off= vector(0, self.bank.height + self.bnk_to_bus_gap)
            self.din1_bus_off= vector(0, self.pow_rail_1_off.y + 2*self.pow_pitch)
            self.dout1_bus_off= vector(0, self.din1_bus_off.y + self.data_bus_height)
            self.v_bus_off= vector(self.bank.width+self.bnk_to_bus_gap+v_off,0)
            
        if self.orien == "V":
            if ((self.w_size+2)*self.pitch>self.sp_mrg_ctrl.height-self.v_bus_width):
                v_off = v_off + (self.w_size+2)*self.pitch-self.sp_mrg_ctrl.height+self.v_bus_width

            self.v_bus_height =self.bank_ack_mrg_off+ 3*self.bank.height + \
                               4*(self.bnk_to_bus_gap + self.data_bus_height + \
                               self.pow_pitch + self.pitch ) + self.bnk_to_bnk_gap
            self.pow_rail_1_off= vector(-v_off,self.bank.height + self.bnk_to_bus_gap)
            self.din1_bus_off= vector(-v_off,self.pow_rail_1_off.y + 2*self.pow_pitch)
            self.dout1_bus_off= vector(-v_off,self.din1_bus_off.y + self.data_bus_height)
            self.pow_rail_2_off= vector(-v_off,3*(self.bank.height + self.bnk_to_bus_gap) +\
                                 self.bnk_to_bnk_gap + 2*(self.data_bus_height +self.pow_pitch))
            self.din2_bus_off= vector(-v_off,self.pow_rail_2_off.y + 2*self.pow_pitch)
            self.dout2_bus_off= vector(-v_off,self.din2_bus_off.y + self.data_bus_height)
            self.v_bus_off= vector(0, 0)

        if self.power_gate:
            self.sleep_off = self.v_bus_off
            self.reset_off= self.sleep_off + vector(self.pitch,0)
        else:
            self.reset_off= self.v_bus_off
        
        self.addr_bus1_off= self.reset_off + vector(self.pitch,0)
        self.S_off= self.addr_bus1_off +vector(self.bank_addr_size*self.pitch,0)
        self.gnd_off= self.S_off +vector(self.pitch,0)
        self.vdd_off= self.gnd_off + vector(self.pitch,0)
        self.sel_bus_off= self.vdd_off + vector(self.pitch,0)
        self.addr_bus2_off= self.sel_bus_off + vector(self.num_banks*self.pitch,0)
        self.spl_mrg_ctrl_bus_off= self.addr_bus2_off + vector(2*self.pitch,0)
        self.spl_mrg_in_off= self.spl_mrg_ctrl_bus_off + vector(5*self.pitch,0)
        self.ctrl_bus_off=self.spl_mrg_in_off+vector(2*self.pitch*self.num_banks,0)

    def add_two_banks(self):
        
        if self.orien == "H":
            # Placement of bank 0 (left)
            self.bank_pos_1= vector(self.bank.width, 2*self.data_bus_height + \
                                    self.bnk_to_bus_gap+ 2*self.pow_pitch)
            self.bank_inst=[self.add_bank(1, self.bank_pos_1, 1, -1)]

            # Placement of bank 1 (right)
            x_off= self.bank.width+max(self.sp_mrg_ctrl.height,self.v_bus_width)+2*self.bnk_to_bus_gap
            self.bank_pos_0= vector(x_off, self.bank_pos_1.y)
            self.bank_inst.append(self.add_bank(0, self.bank_pos_0, 1, 1))
            self.width= self.bank_inst[1].rx() + self.pitch

        if self.orien == "V":
            # Placement of bank 0 (bottom)
            x_off= self.v_bus_width + self.bnk_to_bus_gap
            self.bank_pos_0= vector(x_off,self.bank.height)
            self.bank_inst=[self.add_bank(0, self.bank_pos_0, -1, 1)]

            # Placement of bank 1 (top)
            y_off= self.bank.height +2*(self.data_bus_height+self.bnk_to_bus_gap+self.pow_pitch)
            self.bank_pos_1= vector(self.bank_pos_0.x, y_off)
            self.bank_inst.append(self.add_bank(1, self.bank_pos_1, 1, 1))

            self.width= self.bank_inst[1].rx() + self.pitch
            if (self.sp_mrg_ctrl.height >= self.v_bus_width):
                self.width= self.width + (self.sp_mrg_ctrl.height-self.v_bus_width)
            

        sp_mrg_ctrl_off= vector(self.v_bus_off.x+self.v_bus_width -contact.m1m2.height,
                                self.v_bus_off.y+ self.v_bus_height-self.m1_width)
        # Rotate 90, to pitch-patch in and outs and also poly-silicon goes in one direction
        self.sp_mrg_ctrl_inst= self.add_inst(name="split_merge_control", 
                                              mod=self.sp_mrg_ctrl, 
                                              offset=sp_mrg_ctrl_off,
                                              mirror= "R0",
                                              rotate= 90)
        temp =[]
        if self.two_level_bank:
            temp.extend(["r_split","w_split","rw_split","ack_merge","rack_merge",
                         "rreq_split","wreq_split","wack_merge"])
        else:
            temp.extend(["r","w","rw","ack","rack","rreq","wreq","wack"])
        for i in range(self.num_banks):
            temp.extend(["ack{0}".format(i), "ack_b{0}".format(i)])
        temp.extend(["pre_ack", "pre_wack", "pre_rack", "rw_merge"])        
        if self.two_level_bank:
            temp.extend(["ack_b", "addr_split[{0}]".format(self.addr_size-1)])
        else:
            temp.extend(["ack_b", "addr[{0}]".format(self.addr_size-1)])
        
        if self.two_level_bank:
            temp.extend(["sel[0]", "sel[1]", "S", "vdd", "gnd"])
        else:
            temp.extend(["sel[0]", "sel[1]", "vdd", "vdd", "gnd"])
        
        self.connect_inst(temp)
        
        self.height= max(self.bank_inst[1].uy(), self.sp_mrg_ctrl_inst.uy())

    def add_four_banks(self):
        """ Adds four banks based on orientation """
        
        if self.orien == "H":
            # Placement of bank 3 (upper left)
            self.bank_pos_3= vector(self.bank.width,self.bank.height + 2*self.data_bus_height + \
                                     2*self.bnk_to_bus_gap + 2*self.pow_pitch)
            self.bank_inst=[self.add_bank(3, self.bank_pos_3, 1, -1)]
            
            # Placement of bank 2 (upper right)
            x_off= self.bank.width+max(self.sp_mrg_ctrl.height,self.v_bus_width)+2*self.bnk_to_bus_gap
            self.bank_pos_2= vector(x_off, self.bank_pos_3.y)
            self.bank_inst.append(self.add_bank(2, self.bank_pos_2, 1, 1))

            # Placement of bank 1 (bottom left)
            y_off= self.bank.height
            self.bank_pos_1= vector(self.bank_pos_3.x, y_off)
            self.bank_inst.append(self.add_bank(1, self.bank_pos_1, -1, -1))

            # Placement of bank 0 (bottom right)
            self.bank_pos_0= vector(self.bank_pos_2.x, self.bank_pos_1.y)
            self.bank_inst.append(self.add_bank(0, self.bank_pos_0, -1, 1))

            self.width= self.bank_inst[1].rx() + self.pitch
        
        if self.orien == "V":
            # Placement of bank 0 (lowest)
            x_off= self.v_bus_width + self.bnk_to_bus_gap
            self.bank_pos_0= vector(x_off,self.bank.height)
            self.bank_inst=[self.add_bank(0, self.bank_pos_0, -1, 1)]

            # Placement of bank 1 
            y_off= self.bank.height + 2*(self.data_bus_height+self.bnk_to_bus_gap+self.pow_pitch)
            self.bank_pos_1= vector(self.bank_pos_0.x, y_off)
            self.bank_inst.append(self.add_bank(1, self.bank_pos_1, 1, 1))

            # Placement of bank 2 
            y_off= 3*self.bank.height+2*(self.data_bus_height + \
                   self.bnk_to_bus_gap + self.pow_pitch) + self.bnk_to_bnk_gap
            self.bank_pos_2= vector(self.bank_pos_0.x, y_off)
            self.bank_inst.append(self.add_bank(2, self.bank_pos_2, -1, 1))

            # Placement of bank 3 (topmost)
            y_off= 3*self.bank.height + 4*(self.data_bus_height + \
                    self.bnk_to_bus_gap + self.pow_pitch) + self.bnk_to_bnk_gap
            self.bank_pos_3= vector(self.bank_pos_0.x, y_off)
            self.bank_inst.append(self.add_bank(3, self.bank_pos_3, 1, 1))

            self.width= self.bank_inst[1].rx() + self.pitch
            if (self.sp_mrg_ctrl.height >= self.v_bus_width):
                self.width= self.width+ (self.sp_mrg_ctrl.height -self.v_bus_width)
            
            if ((self.w_size+1)*self.pitch>(self.sp_mrg_ctrl.height-self.v_bus_width)):
                self.width = self.bank_inst[1].rx() + (self.w_size+3)*self.pitch
        
            self.width += self.w_size*self.pitch
            if self.mask:
                self.width += self.w_size*self.pitch
        sp_mrg_ctrl_off= vector(self.v_bus_off.x+self.v_bus_width-self.pitch+1.5*self.m2_width,
                                self.v_bus_off.y+ self.v_bus_height-self.m1_width)
        self.sp_mrg_ctrl_inst= self.add_inst(name="split_merge_control", 
                                             mod=self.sp_mrg_ctrl, 
                                             offset=sp_mrg_ctrl_off,
                                             mirror= "R0",
                                             rotate= 90)
        temp =[]
        if self.two_level_bank:
            temp.extend(["r_split","w_split","rw_split","ack_merge","rack_merge",
                         "rreq_split","wreq_split","wack_merge"])
        else:
            temp.extend(["r","w","rw","ack","rack","rreq","wreq","wack"])
        for i in range(self.num_banks):
            temp.extend(["ack{0}".format(i), "ack_b{0}".format(i)])
        temp.extend(["pre_ack", "pre_wack", "pre_rack", "rw_merge"])        
        if self.two_level_bank:
            temp.append("ack_b")
            for i in range(int(log(self.num_banks,2))):
                temp.append("addr_split[{0}]".format(self.addr_size-2+i))
        else:
            temp.append("ack_b")
            for i in range(int(log(self.num_banks,2))):
                temp.append("addr[{0}]".format(self.addr_size-2+i))
        for i in range(self.num_banks):
            temp.append("sel[{0}]".format(i))

        if self.two_level_bank:
            temp.extend(["S", "vdd", "gnd"])
        else:
            temp.extend(["vdd", "vdd", "gnd"])
        self.connect_inst(temp)
        
        if self.orien == "H":
            self.height= max(self.bank_inst[1].uy(), self.sp_mrg_ctrl_inst.uy())
        
        if self.orien == "V":
            self.height= max(self.bank_inst[3].uy(), self.sp_mrg_ctrl_inst.uy())
        
    def add_single_bank_pins(self):
        """ Add the ctrl, addr bus, Data_in and Data_out buses and power rails. """

        # Vertical bus
        ctrl_pins= ["reset","r","w","rw","ack","rack","rreq","wreq","wack"]
        if self.power_gate:
            ctrl_pins.append("sleep")

        for i in range(len(ctrl_pins)):
            pin = self.bank_inst.get_pin(ctrl_pins[i])
            self.add_layout_pin(text=ctrl_pins[i],
                                layer= "metal1",
                                offset= pin.ll(),
                                width= pin.width(),
                                height= pin.height())
        for i in range(self.addr_size):
            self.add_layout_pin(text="addr[{0}]".format(i),
                                layer= "metal1",
                                offset= self.bank_inst.get_pin("addr[{0}]".format(i)).ll(),
                                width= self.m1_width,
                                height= self.m1_width)

        if self.mask:
            pin_list = ["din", "bm"]
            layer_list = ["metal1", "metal3"]
            stack_list = [self.m1_stack, self.m2_stack]
        else:
            pin_list = ["din"]
            layer_list = ["metal1"]
            stack_list = [self.m1_stack]


        if self.num_subanks==1:
            pin_list.append("dout")
            for i in range(self.w_size):
                for pin in pin_list:
                    off= self.bank_inst.get_pin(pin+"[0][{}]".format(i)).ll()-vector(0,2*self.pow_pitch)
                    self.add_layout_pin(text=pin+"[{0}]".format(i),
                                        layer= "metal2",
                                        offset= off,
                                        width= self.m2_width,
                                        height= self.m2_width)
                    self.add_rect(layer="metal2", 
                                 offset= off, 
                                 width= self.m2_width, 
                                 height= 2*self.pow_pitch)

        if self.num_subanks>1:
            for i in range(self.w_size):
                
                for (pin, layer) in zip(pin_list, layer_list):
                    yoff= self.bank_inst.get_pin(pin+"[0][0]").by()-(i+2)*self.pitch-2*self.pow_pitch
                    height= drc["minwidth_{}".format(layer)]
                    self.add_rect(layer= layer, 
                                  offset= (0, yoff), 
                                  width= self.bank_inst.width, 
                                  height= height)
                    self.add_layout_pin(text=pin+"[{0}]".format(i),
                                        layer= layer,
                                        offset= (0, yoff),
                                        width= self.m1_width,
                                        height= self.m1_width)

                for j in range(self.num_subanks):
                    for (pin, stack) in zip(pin_list, stack_list):
                        pin= self.bank_inst.get_pin(pin+"[{0}][{1}]".format(j, i)).ll()
                        offset= vector(pin.x, yoff)
                        self.add_rect(layer= "metal2", 
                                      offset= (offset.x, offset.y), 
                                      width= self.m2_width, 
                                      height= (i+2)*self.pitch+2*self.pow_pitch)
                        self.add_via(stack,(offset.x, offset.y-self.via_shift("v1")))
            
            for i in range(self.w_size):
                yoff= self.bank_inst.get_pin("dout[0][0]").by()-(i+2+self.w_size)*self.pitch-2*self.pow_pitch
                self.add_rect(layer= "metal1", 
                              offset= (0, yoff), 
                              width= self.bank_inst.width, 
                              height= self.m1_width)
                self.add_layout_pin(text="dout[{0}]".format(i),
                                    layer= "metal1",
                                    offset= (0, yoff),
                                    width= self.m1_width,
                                    height= self.m1_width)
                for j in range(self.num_subanks):
                    pin=self.bank_inst.get_pin("dout[{0}][{1}]".format(j,i)).ll()
                    offset= vector(pin.x, yoff)
                    self.add_rect(layer= "metal2", 
                                  offset= (offset.x, offset.y), 
                                  width= self.m2_width, 
                                  height= (i+2+self.w_size)*self.pitch+2*self.pow_pitch)
                    self.add_via(self.m1_stack,(offset.x, offset.y-self.via_shift("v1")))
        
        power_pin= ["vdd", "gnd"]
        for i in range(2):
            yoff = self.bank_inst.get_pins(power_pin[i])[0].by()-(i+1)*self.pow_pitch
            self.add_rect(layer= "metal3", 
                          offset= (0, yoff), 
                          width= self.bank_inst.width, 
                          height= self.pow_width)
            self.add_layout_pin(text=power_pin[i],
                                layer= "metal3",
                                offset= (0, yoff),
                                width= self.pow_width,
                                height= self.pow_width)
            for j in range(2*self.num_subanks+1):
                offset1= self.bank_inst.get_pins(power_pin[i])[j].ll()
                self.add_via_center(self.m2_stack, (offset1.x, yoff+0.5*self.pow_width-self.m1_width)+self.pow_via_shift, size = [self.num_via,self.num_via])
                self.add_rect(layer="metal2",
                              offset= (offset1.x, yoff),
                              width=self.pow_width,
                              height=(i+1)*self.pow_pitch)

    def add_busses(self):
        """ Add the horizontal and vertical busses """
        
        # The order of the control signals on the control bus matters
        if self.two_level_bank:
            make_pin= False
        else:
            make_pin= True


        if self.power_gate:
            self.v_ctrl_bus_pos= self.create_bus(layer="metal2",
                                                 pitch=self.pitch,
                                                 offset=self.sleep_off,
                                                 names=["sleep"],
                                                 length=self.v_bus_height,
                                                 vertical=True,
                                                 make_pins=make_pin)

            self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                       pitch=self.pitch,
                                                       offset=self.reset_off,
                                                       names=["reset"],
                                                       length=self.v_bus_height,
                                                       vertical=True,
                                                       make_pins=make_pin))
        else:
            self.v_ctrl_bus_pos= self.create_bus(layer="metal2",
                                                 pitch=self.pitch,
                                                 offset=self.reset_off,
                                                 names=["reset"],
                                                 length=self.v_bus_height,
                                                 vertical=True,
                                                 make_pins=True)
        
        if self.two_level_bank:
            addr_bus_names=["addr_split[{0}]".format(i) for i in range(self.bank_addr_size)]
            make_pin= False
        else:
            addr_bus_names=["addr[{0}]".format(i) for i in range(self.bank_addr_size)]
            make_pin= True
        self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                   pitch=self.pitch,
                                                   offset=self.addr_bus1_off,
                                                   names=addr_bus_names,
                                                   length=self.v_bus_height,
                                                   vertical=True,
                                                   make_pins=make_pin))
       
        self.select_name= ["S"]
        self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                   pitch=self.pitch,
                                                   offset=self.S_off,
                                                   names=self.select_name,
                                                   length=self.v_bus_height,
                                                   vertical=True,
                                                   make_pins=False))


        self.gnd_name= ["gnd"]
        self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                   pitch=self.pitch,
                                                   offset=self.gnd_off,
                                                   names=self.gnd_name,
                                                   length=self.v_bus_height,
                                                   vertical=True,
                                                   make_pins=False))

        self.vdd_name= ["vdd"]
        self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                   pitch=self.pitch,
                                                   offset=self.vdd_off,
                                                   names=self.vdd_name,
                                                   length=self.v_bus_height,
                                                   vertical=True,
                                                   make_pins=False))

        if self.num_banks == 2:
            sel_bus_names= ["sel[{0}]".format(i) for i in range(self.num_banks)]
        if self.num_banks == 4:
            sel_bus_names= ["sel[{0}]".format(self.num_banks-1-i) for i in range(self.num_banks)]

        self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                   pitch=self.pitch,
                                                   offset=self.sel_bus_off,
                                                   names=sel_bus_names,
                                                   length=self.v_bus_height,
                                                   vertical=True,
                                                   make_pins=False))

        if self.two_level_bank:
            addr_bus_names=["addr_split[{0}]".format(self.addr_size-1-i) for i in range(int(log(self.num_banks,2)))]
            make_pin= False
        else:
            addr_bus_names=["addr[{0}]".format(self.addr_size-1-i) for i in range(int(log(self.num_banks,2)))]
            make_pin= True
        self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                   pitch=self.pitch,
                                                   offset=self.addr_bus2_off,
                                                   names=addr_bus_names,
                                                   length=self.v_bus_height,
                                                   vertical=True,
                                                   make_pins=make_pin))
        
        bank_spl_mrg_bus_names= ["pre_wack", "pre_rack", "rw_merge", "pre_ack", "ack_b"]
        self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                   pitch=self.pitch,
                                                   offset=self.spl_mrg_ctrl_bus_off,
                                                   names=bank_spl_mrg_bus_names,
                                                   length=self.v_bus_height,
                                                   vertical=True,
                                                   make_pins=False))

        for i in range(self.num_banks):
            self.bank_spl_mrg_input_bus_names= ["ack_b{0}".format(i), "ack{0}".format(i)]
            self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                                       pitch=self.pitch,
                                                       offset=self.spl_mrg_in_off+\
                                                              vector(2*i*self.pitch,0),
                                                       names=self.bank_spl_mrg_input_bus_names,
                                                       length=self.v_bus_height,
                                                       vertical=True,
                                                       make_pins=False))

        if self.two_level_bank:
            ctrl_bus_names=["wack_merge", "wreq_split", "rreq_split", "rack_merge", 
                            "ack_merge", "rw_split", "w_split", "r_split"]
            make_pin= False
        else:
            ctrl_bus_names=["wack", "wreq", "rreq", "rack", "ack", "rw", "w", "r"]
            make_pin= True

        self.v_ctrl_bus_pos.update(self.create_bus(layer="metal2",
                                   pitch=self.pitch,
                                   offset=self.ctrl_bus_off,
                                   names=ctrl_bus_names,
                                   length=self.v_bus_height,
                                   vertical=True,
                                   make_pins=make_pin))

        # Horizontal power rails
        power_rail_names= ["vdd", "gnd"]
        for i in range(2):
            self.add_rect(layer="metal3", 
                          offset=self.pow_rail_1_off+vector(0, i*self.pow_pitch), 
                          width=self.data_bus_width, 
                          height=self.pow_width)
            #if not self.two_level_bank:
            self.add_layout_pin(text=power_rail_names[i], 
                                layer="metal3", 
                                offset=self.pow_rail_1_off+vector(0, i*self.pow_pitch), 
                                width=self.data_bus_width, 
                                height=self.pow_width)
        # Horizontal data bus
        if self.two_level_bank:
            din_bus_names=["din_split[{0}]".format(i) for i in range(self.w_size)]
            bm_bus_names=["bm_split[{0}]".format(i) for i in range(self.w_size)]
            make_pin= False
        else:
            din_bus_names=["din[{0}]".format(i) for i in range(self.w_size)]
            bm_bus_names=["bm[{0}]".format(i) for i in range(self.w_size)]
            make_pin= True

        self.din1_bus_pos= self.create_bus(layer="metal1",
                                           pitch=self.pitch,
                                           offset=self.din1_bus_off,
                                           names=din_bus_names,
                                           length=self.data_bus_width,
                                           vertical=False,
                                           make_pins=make_pin)
        if self.mask:
            self.bm_bus_pos= self.create_bus(layer="metal3",
                            pitch=self.pitch,
                            offset=self.din1_bus_off,
                            names=bm_bus_names,
                            length=self.data_bus_width,
                            vertical=False,
                            make_pins=make_pin)

        if self.two_level_bank:
            dout_bus_names=["dout_merge[{0}]".format(i) for i in range(self.w_size)]
            make_pin= False
        else:
            dout_bus_names=["dout[{0}]".format(i) for i in range(self.w_size)]
            make_pin= True

        self.dout1_bus_pos= self.create_bus(layer="metal1",
                                            pitch=self.pitch,
                                            offset=self.dout1_bus_off,
                                            names=dout_bus_names,
                                            length=self.data_bus_width,
                                            vertical=False,
                                            make_pins=make_pin)
        if (self.num_banks == 4 and  self.orien == "V"):
            for i in range(2):
                self.add_rect(layer="metal3", 
                              offset=self.pow_rail_2_off+vector(0, i*self.pow_pitch), 
                              width=self.data_bus_width, 
                              height=self.pow_width)
                #if not self.two_level_bank:
                self.add_layout_pin(text=power_rail_names[i], 
                                    layer="metal3", 
                                    offset=self.pow_rail_2_off+vector(0, i*self.pow_pitch), 
                                    width=self.data_bus_width, 
                                    height=self.pow_width)

            if self.two_level_bank:
                din_bus_names=["din_split[{0}]".format(i) for i in range(self.w_size)]
                if self.mask:
                    bm_bus_names=["bm_split[{0}]".format(i) for i in range(self.w_size)]

            else:
                din_bus_names=["din[{0}]".format(i) for i in range(self.w_size)]
                if self.mask:
                    bm_bus_names=["bm[{0}]".format(i) for i in range(self.w_size)]

            self.din2_bus_pos= self.create_bus(layer="metal1",
                                               pitch=self.pitch,
                                               offset=self.din2_bus_off,
                                               names=din_bus_names,
                                               length=self.data_bus_width,
                                               vertical=False,
                                               make_pins=False)
            if self.mask:
                self.bm_bus_pos= self.create_bus(layer="metal3",
                                pitch=self.pitch,
                                offset=self.din2_bus_off,
                                names=bm_bus_names,
                                length=self.data_bus_width,
                                vertical=False,
                                make_pins=make_pin)
            
            if self.two_level_bank:
                dout_bus_names=["dout_merge[{0}]".format(i) for i in range(self.w_size)]
            else:
                dout_bus_names=["dout[{0}]".format(i) for i in range(self.w_size)]
            self.dout2_bus_pos= self.create_bus(layer="metal1",
                                                pitch=self.pitch,
                                                offset=self.dout2_bus_off,
                                                names=dout_bus_names,
                                                length=self.data_bus_width,
                                                vertical=False,
                                                make_pins=False)

    def route_banks(self):
        """ Connect the inputs and outputs of each bank to horizontal and vertical busses """
        
        # Data Connections
        if (self.num_banks == 2 or self.orien == "H"):
            for k in range(self.num_banks):
                for i in range(self.num_subanks):
                  for j in range(self.w_size):
                      din_off= vector(self.bank_inst[k].get_pin("din[{0}][{1}]".format(i,j)).lx(), 
                                      self.din1_bus_off.y+ j*self.pitch + 0.5*self.m1_width)
                      din_height=  self.bank_inst[k].get_pin("din[{0}][{1}]".format(i,j)).by() -\
                                   self.din1_bus_off.y - j*self.pitch
                      self.add_rect(layer="metal2", 
                                    offset=din_off, 
                                    width=self.m2_width, 
                                    height=din_height)
                      self.add_via(self.m1_stack, (din_off.x, din_off.y-self.via_shift("v1")))
                      
                      if self.mask:
                          bm_off= vector(self.bank_inst[k].get_pin("bm[{0}][{1}]".format(i,j)).lx(), 
                                          self.din1_bus_off.y+ j*self.pitch + 0.5*self.m1_width)
                          self.add_rect(layer="metal2", 
                                        offset=bm_off, 
                                        width=self.m2_width, 
                                        height=din_height)
                          self.add_via(self.m2_stack, (bm_off.x, bm_off.y-self.via_shift("v1")))
    
                      
                      dout_off= vector(self.bank_inst[k].get_pin("dout[{0}][{1}]".format(i,j)).lx(), 
                                       self.dout1_bus_off.y+ j*self.pitch + 0.5*self.m1_width)
                      dout_height=  self.bank_inst[k].get_pin("dout[{0}][{1}]".format(i,j)).by() -\
                                    self.dout1_bus_off.y - j*self.pitch
                      self.add_rect(layer="metal2", 
                                    offset=dout_off, 
                                    width=self.m2_width, 
                                    height=dout_height)
                      self.add_via(self.m1_stack, (dout_off.x, dout_off.y-self.via_shift("v1")))
        
        if (self.num_banks == 4 and  self.orien == "V"):
            for k in range(self.num_banks):
                for i in range(self.num_subanks):
                  for j in range(self.w_size):
                      self.data_in_bus_off= [self.din1_bus_off.y, self.din2_bus_off.y]
                      self.data_out_bus_off= [self.dout1_bus_off.y, self.dout2_bus_off.y]
                      din_off= vector(self.bank_inst[k].get_pin("din[{0}][{1}]".format(i,j)).lx(), 
                                      self.data_in_bus_off[k//2]+ j*self.pitch + 0.5*self.m1_width)
                      din_height=  self.bank_inst[k].get_pin("din[{0}][{1}]".format(i,j)).by() - \
                                   self.data_in_bus_off[k//2] - j*self.pitch
                      self.add_rect(layer="metal2", 
                                    offset=din_off, 
                                    width=self.m2_width, 
                                    height=din_height)
                      self.add_via(self.m1_stack, (din_off.x, din_off.y-self.via_shift("v1")))
                      if self.mask:
                          bm_off= vector(self.bank_inst[k].get_pin("bm[{0}][{1}]".format(i,j)).lx(), 
                                         self.data_in_bus_off[k//2]+ j*self.pitch + 0.5*self.m1_width)
                          self.add_rect(layer="metal2", 
                                        offset=bm_off, 
                                        width=self.m2_width, 
                                        height=din_height)
                          self.add_via(self.m2_stack, (bm_off.x, bm_off.y-self.via_shift("v1")))
    
                      dout_off= vector(self.bank_inst[k].get_pin("dout[{0}][{1}]".format(i,j)).lx(), 
                                self.data_out_bus_off[k//2]+ j*self.pitch + 0.5*self.m1_width)
                      dout_height=  self.bank_inst[k].get_pin("dout[{0}][{1}]".format(i,j)).by() -\
                                    self.data_out_bus_off[k//2] - j*self.pitch
                      self.add_rect(layer="metal2", 
                                    offset=dout_off, 
                                    width=self.m2_width, 
                                    height=dout_height)
                      self.add_via(self.m1_stack, (dout_off.x, dout_off.y-self.via_shift("v1")))
                      
            # Connect second Data_in & Data_out bus to first one
            for j in range(self.w_size):                      

                doutoff1= vector(self.dout1_bus_off.x, self.dout1_bus_off.y + j*self.pitch + self.m1_width)
                doutoff2= vector(-(j+2)*self.pitch, doutoff1.y)
                doutoff3= vector(doutoff2.x, self.dout2_bus_off.y + j*self.pitch + self.m1_width)
                doutoff4= vector(self.dout2_bus_off.x, doutoff3.y)
                self.add_wire(self.m1_stack, [doutoff1, doutoff2, doutoff3, doutoff4])
                

                dinoff1= vector(self.din1_bus_off.x+self.data_bus_width, self.din1_bus_off.y + j*self.pitch + self.m1_width)
                dinoff2= vector(dinoff1.x+(j+1)*self.pitch, dinoff1.y)
                dinoff3= vector(dinoff2.x,  self.din2_bus_off.y + j*self.pitch + self.m1_width)
                dinoff4= vector(self.din2_bus_off.x, dinoff3.y)
                self.add_wire(self.m1_stack, [dinoff1, dinoff2, dinoff3, dinoff4])
                      
                if self.mask:
                    bmoff1= vector(self.din1_bus_off.x+self.data_bus_width, self.din1_bus_off.y + j*self.pitch + self.m3_width)
                    bmoff2= vector(bmoff1.x+(j+1+self.w_size)*self.pitch, bmoff1.y)
                    bmoff3= vector(bmoff2.x,  self.din2_bus_off.y + j*self.pitch + self.m3_width)
                    bmoff4= vector(self.din2_bus_off.x, bmoff3.y)
                    self.add_wire(self.m2_rev_stack, [bmoff1, bmoff2, bmoff3, bmoff4])

        # Addr Connections
        for k in range(self.num_banks):
            for i in range(self.bank_addr_size):
                pin= self.bank_inst[k].get_pin("addr[{0}]".format(i))
                if pin.layer[0:6] == "metal1":
                    layer= "metal1"
                    height= self.m1_width
                    stack= self.m1_stack
                else:
                    layer= "metal3"
                    height= self.m3_width
                    stack= self.m2_stack

                addr_off= vector(self.addr_bus1_off.x+ i*self.pitch- self.metal3_enclosure_via2, 
                                 self.bank_inst[k].get_pin("addr[{0}]".format(i)).uc().y - height)
                addr_width=  self.bank_inst[k].get_pin("addr[{0}]".format(i)).uc().x - \
                             self.addr_bus1_off.x - i*self.pitch

                self.add_rect(layer=layer, 
                              offset=addr_off, 
                              width=addr_width, 
                              height=height)
                self.add_via(stack, (addr_off.x, addr_off.y-self.via_shift("v1")))
        
        # bank_sel Connections
        for k in range(self.num_banks):
            pin= self.bank_inst[k].get_pin("S")
            if pin.layer[0:6] == "metal1":
                layer= "metal1"
                height= self.m1_width
                stack= self.m1_stack
            else:
                layer= "metal3"
                height= self.m3_width
                stack= self.m2_stack

            bank_sel_off= vector(self.sel_bus_off.x+ k*self.pitch, 
                                 self.bank_inst[k].get_pin("S").uc().y - height)
            bank_sel_width=  self.bank_inst[k].get_pin("S").uc().x - \
                             self.sel_bus_off.x - k*self.pitch
            self.add_rect(layer=layer, 
                          offset=bank_sel_off, 
                          width=bank_sel_width, 
                          height=height)
            self.add_via(stack, (bank_sel_off.x, bank_sel_off.y-self.via_shift("v1")))
    
        # Ctrl Connections
        for k in range(self.num_banks):
            control_pin_list= ["reset", "wack", "wreq", "rreq", "rack", "ack", "rw", "w", "r", 
                               "ack_merge", "rw_en1_S", "rw_en2_S", "Mack", "Mrack", "Mwack", "Mdout"]
            
            if self.two_level_bank:
                split_control_list= ["reset", "pre_wack", "wreq_split", "rreq_split", "pre_rack", 
                                     "pre_ack", "rw_split", "w_split", "r_split", "ack{0}".format(k), 
                                     "ack_b{0}".format(k), "ack_b", "rw_merge", "rreq_split", "wreq_split", "rack_merge"]
            else:
                split_control_list= ["reset", "pre_wack", "wreq", "rreq", "pre_rack", "pre_ack",  
                                     "rw", "w", "r", "ack{0}".format(k), "ack_b{0}".format(k),"ack_b", 
                                     "rw_merge", "rreq", "wreq", "rack"]
  
            if self.power_gate:
                 control_pin_list.append("sleep")
                 split_control_list.append("sleep")

            for i in range(len(control_pin_list)):
                pin= self.bank_inst[k].get_pin(control_pin_list[i])
                if pin.layer[0:6] == "metal1":
                    layer= "metal1"
                    height= self.m1_width
                    stack= self.m1_stack
                else:
                    layer= "metal3"
                    height= self.m3_width
                    stack= self.m2_stack
                    
                ctrl_off= vector(self.v_ctrl_bus_pos[split_control_list[i]].cx()- 0.5*height, 
                                 self.bank_inst[k].get_pin(control_pin_list[i]).uc().y- height)
                ctrl_width=  self.bank_inst[k].get_pin(control_pin_list[i]).uc().x - \
                             self.v_ctrl_bus_pos[split_control_list[i]].cx()
                self.add_rect(layer=layer, 
                              offset=ctrl_off, 
                              width=ctrl_width, 
                              height=height)
                self.add_via(stack, (ctrl_off.x, ctrl_off.y-self.via_shift("v1")))             
        
        
        # select= vdd Connection
        if not self.two_level_bank:
            sel_pos1=vector(self.v_ctrl_bus_pos["S"].cx(), self.v_ctrl_bus_pos["S"].by()+self.m1_width)
            sel_pos2=vector(self.v_ctrl_bus_pos["vdd"].cx(), self.v_ctrl_bus_pos["vdd"].by()+self.m1_width)
            self.add_path("metal1", [sel_pos1, sel_pos2])
            self.add_via(self.m1_stack, (sel_pos1.x-0.5*self.m2_width, 
                         sel_pos1.y-0.5*self.m1_width-self.via_shift("v1")))
            self.add_via(self.m1_stack, (sel_pos2.x-0.5*self.m2_width, 
                         sel_pos2.y-0.5*self.m1_width-self.via_shift("v1")))
        
        
        # vdd and gnd Connections
        if (self.num_banks == 2 or self.orien == "H"):
            for k in range(self.num_banks):
                for vdd_pin in self.bank_inst[k].get_pins("vdd"):
                    vdd_off= vector(vdd_pin.lx(), self.pow_rail_1_off.y + 0.5*self.m1_width)
                    vdd_height=  vdd_pin.by() - self.pow_rail_1_off.y
                    self.add_rect(layer="metal2", 
                                  offset=vdd_off, 
                                  width=self.pow_width, 
                                  height=vdd_height)
                    self.add_via_center(self.m2_stack, (vdd_off.x, vdd_off.y)+self.pow_via_shift, size=[self.num_via, self.num_via])
        
                for gnd_pin in self.bank_inst[k].get_pins("gnd"):
                    gnd_off= vector(gnd_pin.lx(), 
                                    self.pow_rail_1_off.y + self.pow_pitch + 0.5*self.m1_width)
                    gnd_height=  gnd_pin.by() - self.pow_rail_1_off.y - self.pow_pitch
                    self.add_rect(layer="metal2", 
                                  offset=gnd_off, 
                                  width=self.pow_width, 
                                  height=gnd_height)
                    self.add_via_center(self.m2_stack, (gnd_off.x, gnd_off.y)+self.pow_via_shift, size=[self.num_via, self.num_via])

        if (self.num_banks == 4 and  self.orien == "V"):
            self.power_rail_off= [self.pow_rail_1_off.y, self.pow_rail_2_off.y]
            for k in range(self.num_banks):
                for vdd_pin in self.bank_inst[k].get_pins("vdd"):
                    vdd_off= vector(vdd_pin.lx(), self.power_rail_off[k//2] + 0.5*self.m1_width)
                    vdd_height=  vdd_pin.by() - self.power_rail_off[k//2]
                    self.add_rect(layer="metal2", 
                                  offset=vdd_off, 
                                  width=self.pow_width, 
                                  height=vdd_height)
                    self.add_via_center(self.m2_stack, (vdd_off.x, vdd_off.y)+self.pow_via_shift, size=[self.num_via, self.num_via])
                
                for gnd_pin in self.bank_inst[k].get_pins("gnd"):
                    gnd_off= vector(gnd_pin.lx(), self.power_rail_off[k//2] + \
                                    self.pow_pitch + 0.5*self.m1_width)
                    gnd_height=  gnd_pin.by() - self.power_rail_off[k//2] - self.pow_pitch
                    self.add_rect(layer="metal2", 
                                  offset=gnd_off, 
                                  width=self.pow_width, 
                                  height=gnd_height)
                    self.add_via_center(self.m2_stack, (gnd_off.x, gnd_off.y)+self.pow_via_shift, size=[self.num_via, self.num_via])

        #Connect vdd & gnd of split_merge_control to horizontal vdd & gnd power rails
        self.add_via_center(self.m2_stack, (self.vdd_off.x+0.5*self.m2_width, self.pow_rail_1_off.y+0.5*self.pow_width), size=[1, self.num_via])
        self.add_via_center(self.m2_stack, (self.gnd_off.x+0.5*self.m2_width, self.pow_rail_1_off.y+self.pow_pitch+0.5*self.pow_width), size=[1, self.num_via])

        if (self.num_banks == 4 and  self.orien == "V"):
            self.add_via(self.m2_stack, (self.vdd_off.x-self.via_shift("v2"), self.pow_rail_2_off.y+\
                        0.5*self.m1_width-self.via_shift("v1")), size=[1, self.num_via])
            self.add_via(self.m2_stack, 
                        (self.gnd_off.x-self.via_shift("v2"),self.pow_rail_2_off.y+self.pow_pitch+\
                         0.5*self.m1_width-self.via_shift("v1")), size=[1, self.num_via])


#/////////////////////////////////////////////////////////////////////////////#
#                                                                             #
#  Adding Split and Merge cells and Connection if self.two_level_bank == True #
#                                                                             #
#/////////////////////////////////////////////////////////////////////////////#

    def add_split_merge_cells(self):
        """ Adding the second-level data_split_merge_cells for data, addr and ctrls"""
        
        # Adding data_in_split_cell_array
        #x_off= self.bank_pos_0.x + self.bank.width-2*self.pow_pitch-self.pitch - self.dsplit_ary.width
        x_off=self.bank_inst[1].get_pin("din[{0}][0]".format(self.num_subanks-1)).uc().x-self.dsplit_ary.get_pin("D[0]").uc().x 
        if (self.num_banks == 2 and self.orien=="H"):
            y_off= -(max(self.addr_size,self.control_size)+3)*self.pitch-\
                     self.dsplit_ary.height
        else:
            y_off= -(max(max(self.addr_size,self.control_size), self.w_size)+3)*self.pitch-\
                     self.dsplit_ary.height

        self.dsplit_ary_inst= self.add_inst(name="outter_data_split_array", 
                                            mod=self.dsplit_ary, 
                                            offset=vector(x_off,y_off))
        temp= []
        for i in range(self.w_size):
            temp.append("din[{0}]".format(i))
            temp.append("din_split[{0}]".format(i))
        if self.mask:
            for i in range(self.w_size):
                temp.append("bm[{0}]".format(i))
                temp.append("bm_split[{0}]".format(i))
            
        temp.extend(["rw_en1_S", "rw_en2_S", "reset", "S", "vdd", "gnd"])
        self.connect_inst(temp)

        for i in range(self.w_size):
            if i%2:
                off=self.dsplit_ary_inst.get_pin("D[{0}]".format(i)).ll()
            else:
                off=self.dsplit_ary_inst.get_pin("D[{0}]".format(i)).lr()-vector(self.m2_width,0)
            
            self.add_layout_pin(text="din[{0}]".format(i), 
                                layer="metal2", 
                                offset= off,
                                width=self.m2_width, 
                                height=self.m2_width)
            if self.mask:
                if i%2:
                    off=self.dsplit_ary_inst.get_pin("bm_in[{0}]".format(i)).ll()
                else:
                    off=self.dsplit_ary_inst.get_pin("bm_in[{0}]".format(i)).lr()-vector(self.m2_width,0)

                self.add_layout_pin(text="bm[{0}]".format(i), 
                                    layer="metal2", 
                                     offset= off,
                                     width=self.m2_width, 
                                    height=self.m2_width)


        # Adding data_out_merge_cell_array
        if self.orien == "H":
            #x_off= self.bank_pos_1.x - self.bank.width + self.w_per_row*self.ctrl_mrg_cell.width
            x_off=self.bank_inst[0].get_pin("dout[{0}][0]".format(self.num_subanks-1)).lx()-self.dmerge_ary.get_pin("Q[{}]".format(self.w_size-1)).lx()
            self.dmerge_ary_inst= self.add_inst(name="outter_data_merge_array", 
                                                mod=self.dmerge_ary, 
                                                offset=vector(x_off,y_off))
            temp= []
            for i in range(self.w_size):
                temp.append("dout_merge[{0}]".format(i))
                temp.append("dout[{0}]".format(i))
            temp.extend(["rack_merge", "Mdout", "reset", "S", "vdd", "gnd"])
            self.connect_inst(temp)
        
            for i in range(self.w_size):
                self.add_layout_pin(text="dout[{0}]".format(self.w_size-1-i), 
                                    layer="metal2", 
                                    offset= self.dmerge_ary_inst.get_pin("Q[{0}]".format(i)).ll(),
                                    width=self.m2_width, 
                                    height=self.m2_width)
        
        # Redefining width and height after adding split and merge arrays
        if self.num_banks == 2:
            self.width= self.bank_inst[1].rx()
            # 8 m1 pitch fo split and merge control signals
            self.height= max(self.bank_inst[1].uy(), self.sp_mrg_ctrl_inst.uy()) -\
                             self.dsplit_ary_inst.by() + 8*self.pitch

        if self.num_banks == 4:
            self.width= self.bank_inst[1].rx() + 2*self.w_size*self.pitch
            if self.mask:
                self.width+=(self.w_size+1)*self.pitch
            # 8 m1 pitch fo split and merge control signals
            self.height= max(self.bank_inst[1].uy(), self.sp_mrg_ctrl_inst.uy()) -\
                             self.dsplit_ary_inst.by() + 8*self.pitch

        if self.orien == "V":
            x_off2= self.bank_pos_0.x + self.bank.width - self.dsplit_ary.width
            if self.num_banks == 2:
                y_off2= self.bank_pos_1.y + self.bank.height +\
                        self.dmerge_ary.height + (self.w_size+2)*self.pitch
            if self.num_banks == 4:
                y_off2= self.bank_pos_3.y + self.bank.height + \
                        self.dmerge_ary.height + (self.w_size+2)*self.pitch
            self.dmerge_ary_inst= self.add_inst(name="outter_data_merge_array", 
                                                 mod=self.dmerge_ary, 
                                                 offset=vector(x_off2,y_off2),
                                                 mirror= "MX")
            temp= []
            for i in range(self.w_size):
                temp.append("dout_merge[{0}]".format(i))
                temp.append("dout[{0}]".format(i))
            temp.extend(["rack_merge", "Mdout", "reset", "S", "vdd", "gnd"])
            self.connect_inst(temp)
        
            for i in range(self.w_size):
                self.add_layout_pin(text="dout[{0}]".format(i), 
                                    layer="metal2", 
                                    offset= (self.dmerge_ary_inst.get_pin("Q[{0}]".format(i)).lx(),
                                             self.dmerge_ary_inst.uy()-self.m2_width),
                                    width=self.m2_width, 
                                    height=self.m2_width)

            self.width= self.bank_inst[1].rx() + (self.sp_mrg_ctrl.height-self.v_bus_width)+\
                        (self.w_size+7)*self.pitch
            if self.mask:
                self.width = self.width + (self.w_size+1)*self.pitch

            self.height= max(self.sp_mrg_ctrl_inst.uy(), self.dmerge_ary_inst.uy()) -\
                         self.dsplit_ary_inst.by() + 8*self.pitch + (self.w_size+1)*self.pitch
            
            
            
            if ((self.w_size+1)*self.pitch>(self.sp_mrg_ctrl.height-self.v_bus_width)):
                self.width = self.bank_inst[1].rx() + (self.w_size+7)*self.pitch
                if self.mask:
                    self.width = self.width + (self.w_size+1)*self.pitch

        # Adding addr_split_cell_array
        x_off= self.reset_off.x + self.pitch
        self.addr_split_ary_inst=self.add_inst(name="outter_address_split_array", 
                                               mod=self.addr_split_ary,
                                               offset=vector(x_off,y_off))
        temp= []
        for i in range(self.addr_size):
            temp.append("addr[{0}]".format(i))
            temp.append("addr_split[{0}]".format(i))
        temp.extend(["rw_en1_S", "rw_en2_S", "reset", "S", "vdd", "gnd"])
        self.connect_inst(temp)
        
        for i in range(self.addr_size):
            self.add_layout_pin(text="addr[{0}]".format(i), 
                                layer="metal2", 
                                offset= self.addr_split_ary_inst.get_pin("D[{0}]".format(i)).ll(),
                                width=self.m2_width, 
                                height=self.m2_width)
        
        # Adding rw_split_cell_array
        # 7 m1 pitch gap between ctrl split cells for en1, en2, s, vdd, gnd + two spaces on each side
        self.ctrl_split_gap= 8*self.pitch
        x_off= max(self.sp_mrg_ctrl_inst.rx() + self.ctrl_split_gap, 
                   self.addr_split_ary_inst.rx() + self.ctrl_split_gap)
        self.ctrl_split_ary_inst= self.add_inst(name="outter_ctrl_split_array", 
                                                mod=self.ctrl_split_ary, 
                                                offset=vector(x_off,y_off))
        temp= []
        temp.extend(["r", "r_split", "w", "w_split", "rw", "rw_split"])
        temp.extend(["rreq", "rreq_split", "wreq", "wreq_split"])
        temp.extend(["rw_en1_S", "rw_en2_S", "reset", "S", "vdd", "gnd"])
        self.connect_inst(temp)

        control_pin_name=["r", "w", "rw", "rreq", "wreq"]
        for i in range(5):
            self.add_layout_pin(text=control_pin_name[i], 
                                layer="metal2", 
                                offset= self.ctrl_split_ary_inst.get_pin("D[{0}]".format(i)).ll(),
                                width=self.m2_width, 
                                height=self.m2_width)
        
        # Adding ack_merge_cell
        x_off= self.ctrl_split_ary_inst.rx() + self.ctrl_split_gap
        self.ack_mrg_inst=self.add_inst(name="outter_ack_merge_cell", 
                                        mod=self.ctrl_mrg_cell,
                                        offset=vector(x_off,y_off))

        self.connect_inst(["ack_merge", "ack", "Mack_S", "rw_merge", "reset", "S", "vdd", "gnd"])
        self.add_layout_pin(text="ack", 
                            layer="metal2", 
                            offset= self.ack_mrg_inst.get_pin("Q[0]").ll(),
                            width=self.m2_width, 
                            height=self.m2_width)

        # Adding rack_merge_cell
        x_off= self.ack_mrg_inst.rx() + self.ctrl_split_gap
        self.rack_mrg_inst=self.add_inst(name="outter_rack_merge_cell", 
                                         mod=self.ctrl_mrg_cell,
                                         offset=vector(x_off,y_off))
        self.connect_inst(["rack_merge", "rack", "Mrack_S", "rreq_split", "reset", "S", "vdd", "gnd"])
        self.add_layout_pin(text="rack", 
                            layer="metal2", 
                            offset= self.rack_mrg_inst.get_pin("Q[0]").ll(),
                            width=self.m2_width, 
                            height=self.m2_width)

        # Adding wack_merge_cell
        x_off= self.rack_mrg_inst.rx() + self.ctrl_split_gap
        self.wack_mrg_inst=self.add_inst(name="outter_wack_merge_cell", 
                                         mod=self.ctrl_mrg_cell,
                                         offset=vector(x_off,y_off))
        self.connect_inst(["wack_merge", "wack", "Mwack_S", "wreq_split", "reset", "S", "vdd", "gnd"])
        self.add_layout_pin(text="wack", 
                            layer="metal2", 
                            offset= self.wack_mrg_inst.get_pin("Q[0]").ll(),
                            width=self.m2_width, 
                            height=self.m2_width)

    def route_data_split_merge(self):
        """ Connecting data_split_merge_cells to horizontal data bus"""
        
        # Adding a horizontal bus to connect datain pins to data_split_cell_array
        # Add +-0.5*self.m1_width for center of bus
        self.dsplitoff={}
        self.bmsplitoff={}
        if (self.num_banks == 2 and self.orien == "H"):
            for i in range(self.w_size):
                self.dsplitoff[i]= vector(self.din1_bus_off.x,self.din1_bus_off.y+\
                                          i*self.pitch+0.5*self.m1_width)

        else:
            for i in range(self.w_size):
                self.dsplitoff[i]= vector(self.bank_pos_0.x+self.bank.width-self.dsplit_ary.width-2*self.pow_pitch,
                                          self.reset_off.y-(i+1)*self.pitch-0.5*self.m1_width)

                offset=(self.dsplitoff[i].x-self.ctrl_mrg_cell.width,self.dsplitoff[i].y)
                self.add_rect(layer="metal1", 
                              offset= offset, 
                              width= self.dsplit_ary.width+2*self.pow_pitch+self.ctrl_mrg_cell.width, 
                              height= self.m1_width)
        
                if self.mask: 
                    self.add_rect(layer="metal3", 
                                  offset= offset, 
                                  width= self.dsplit_ary.width+2*self.pow_pitch+self.ctrl_mrg_cell.width, 
                                  height= self.m3_width)

                din_pos_x= self.din1_bus_pos["din_split[{0}]".format(i)].lx()+self.data_bus_width
                din_pos_y= self.din1_bus_pos["din_split[{0}]".format(i)].cy()
                self.add_wire(self.m1_stack, 
                              [(din_pos_x, din_pos_y), 
                              (din_pos_x+(i+1)*self.pitch,din_pos_y),
                              (din_pos_x+(i+1)*self.pitch,self.dsplitoff[i].y),
                              (self.dsplitoff[i].x, self.dsplitoff[i].y+0.5*self.m1_width)]) 
                if self.mask:
                    shift= abs(self.m3_width-self.m1_width)
                    self.add_wire(self.m2_rev_stack, 
                                  [(din_pos_x, din_pos_y+shift), 
                                  (din_pos_x+(i+1+self.w_size)*self.pitch,din_pos_y+shift),
                                  (din_pos_x+(i+1+self.w_size)*self.pitch,self.dsplitoff[i].y),
                                  (self.dsplitoff[i].x, self.dsplitoff[i].y+0.5*self.m3_width)]) 


        # connecting data_in_split_array to data_in_split_bus
        for i in range(self.w_size):
            din_pos= self.dsplit_ary_inst.get_pin("Q[{0}]".format(i)).uc()-vector(0, self.m2_width)
            #x_off= self.bank_inst[self.num_banks-1].get_pin("din[{0}][{1}]".format(self.num_subanks-1,i)).lx()
            y_off= self.dsplitoff[i].y+0.5*self.m2_width
            mid_pos=vector(self.bank_inst[1].get_pin("din[{0}][{1}]".format(self.num_subanks-1, i)).uc().x, y_off)
            #self.add_via_center(self.m1_stack, (din_pos.x, y_off))
            self.add_path("metal2", [din_pos, mid_pos, (din_pos.x, y_off)])
            if (self.num_banks==4 or self.orien == "V"):
                self.add_via_center(self.m1_stack, (din_pos.x, y_off))

            if self.mask:
                bm_pos= self.dsplit_ary_inst.get_pin("bm_out[{0}]".format(i)).uc()-vector(0, self.m2_width)
                y_off= self.dsplitoff[i].y+0.5*self.m3_width
                #x_off= self.bank_inst[self.num_banks-1].get_pin("bm[{0}][{1}]".format(self.num_subanks-1,i)).lx()
                mid_pos=vector(self.bank_inst[1].get_pin("bm[{0}][{1}]".format(self.num_subanks-1, i)).uc().x, y_off)
                
                #self.add_via_center(self.m2_stack, (bm_pos.x, y_off))
                self.add_path("metal2", [bm_pos, mid_pos, (bm_pos.x, y_off)])
                if (self.num_banks==4 or self.orien == "V"):
                    self.add_via_center(self.m2_stack, (bm_pos.x, y_off))

        # Adding a horizontal bus to connect dataout pins to data_merge_cell_array
        self.dmrgoff={}
        if self.orien == "H":
            if self.num_banks == 2:
                for i in range(self.w_size):
                    self.dmrgoff[i]= vector(self.dout1_bus_off.x,self.dout1_bus_off.y+\
                                            i*self.pitch+0.5*self.m1_width)
            if self.num_banks == 4:
                for i in range(self.w_size):
                    self.dmrgoff[i]= vector(self.bank_pos_1.x-self.bank.width, 
                                            self.reset_off.y- (i+1)*self.pitch)
                    self.add_rect(layer="metal1", 
                                  offset=self.dmrgoff[i], 
                                  width= self.dmerge_ary.width+self.ctrl_mrg_cell.width+2*self.pow_pitch, 
                                  height= self.m1_width)

                    data_out_pos_x= self.dout1_bus_pos["dout_merge[{0}]".format(i)].lx()
                    data_out_pos_y= self.dout1_bus_pos["dout_merge[{0}]".format(i)].cy()
                    self.add_wire(self.m1_stack, 
                                  [(data_out_pos_x, data_out_pos_y),
                                  (data_out_pos_x-(i+1)*self.pitch, data_out_pos_y),
                                  (data_out_pos_x-(i+1)*self.pitch, self.dmrgoff[i].y),
                                  (self.dmrgoff[i].x, 
                                   self.dmrgoff[i].y+0.5*self.m1_width)]) 

        if self.orien == "V":
            for i in range(self.w_size):
                x_off= self.bank_pos_0.x+self.bank.width-self.dmerge_ary.width
                if self.num_banks == 2:
                    y_off= self.bank_pos_1.y + self.bank.height+(i+1)*self.pitch
                if self.num_banks == 4:
                    y_off= self.bank_pos_3.y + self.bank.height+(i+1)*self.pitch
                self.dmrgoff[i]= vector(x_off, y_off)
                self.add_rect(layer="metal1", 
                              offset=(self.dmrgoff[i].x-self.ctrl_mrg_cell.width,self.dmrgoff[i].y), 
                              width= self.dmerge_ary.width, 
                              height= self.m1_width)

            for i in range(self.w_size):
                if self.num_banks == 2:
                    data_out_pos_x= self.dout1_bus_pos["dout_merge[{0}]".format(i)].lx()+\
                                    self.data_bus_width
                    data_out_pos_y= self.dout1_bus_pos["dout_merge[{0}]".format(i)].cy()
                if self.num_banks == 4:
                    data_out_pos_x= self.dout2_bus_pos["dout_merge[{0}]".format(i)].lx()+\
                                    self.data_bus_width
                    data_out_pos_y= self.dout2_bus_pos["dout_merge[{0}]".format(i)].cy()
                self.add_wire(self.m1_stack, [(data_out_pos_x, data_out_pos_y),
                             (data_out_pos_x+(i+1)*self.pitch, data_out_pos_y),
                             (data_out_pos_x+(i+1)*self.pitch, self.dmrgoff[i].y),
                             (self.dmrgoff[i].x,self.dmrgoff[i].y+0.5*self.m1_width)]) 


        # connecting data_out_merge_array to data_out_merge_bus
        for i in range(self.w_size):
            x_off= self.bank_inst[0].get_pin("dout[{0}][{1}]".format(self.num_subanks-1,i)).lx()
            y_off= self.dmrgoff[i].y

            if self.orien=="V":
                data_out_pos= self.dmerge_ary_inst.get_pin("D[{0}]".format(i)).uc()
                pos1=vector(data_out_pos.x, y_off)
                pos2=vector(data_out_pos.x, data_out_pos.y+self.m2_width)
            if self.orien=="H":
                data_out_pos= self.dmerge_ary_inst.get_pin("D[{0}]".format(self.w_size-1-i)).uc()
                pos1=vector(x_off+0.5*contact.m1m2.width, y_off)
                pos2=vector(data_out_pos.x, data_out_pos.y-self.m2_width)
            
            
            
            if i%2:
                if self.orien=="H":
                    mid_pos1=vector(pos1.x, pos2.y+self.pitch)
                if self.orien=="V":
                    mid_pos1=vector(pos1.x, pos2.y-self.pitch)

            else:
                mid_pos1=vector(pos1.x, pos2.y)
            
            mid_pos2=vector(pos2.x, mid_pos1.y)
            self.add_path("metal2", [pos1, mid_pos1, mid_pos2, pos2], width=contact.m1m2.width)
            if (self.num_banks == 4 or self.orien=="V"):
                self.add_via(self.m1_stack, (pos1.x+0.5*contact.m1m2.height, y_off), rotate=90)


    def route_addr_ctrl_split_merge(self):
        # Connecting addr_split and ctrl_split_merge_cells to vertical addr & ctrl bus
        
        # Connecting vertical addr bus to addr split cells
        for i in range(self.addr_size):
            addr_split_y_off= self.reset_off.y- (i+1)*self.pitch
            addr_bus_pos= self.v_ctrl_bus_pos["addr_split[{0}]".format(self.addr_size-1-i)].bc()
            addr_split_pos= self.addr_split_ary_inst.get_pin("Q[{0}]".format(self.addr_size-1-i)).uc()
            self.add_path("metal3", [addr_split_pos,(addr_split_pos[0],addr_split_y_off),
                         (addr_bus_pos[0],addr_split_y_off) ])
            self.add_via(self.m2_stack, (addr_split_pos[0]-0.5*self.m3_width,
                                         addr_split_pos[1]-0.5*self.m3_width))
            self.add_via(self.m2_stack,(addr_bus_pos[0]-0.5*self.m3_width,
                                        addr_split_y_off-0.5*self.m3_width-self.via_shift("v2")))
            self.add_path("metal2",[(addr_bus_pos[0],addr_split_y_off),addr_bus_pos ])
        
        # Connecting vertical ctrl bus to ctrlr split/merge cells
        control_pin_list= ["r_split", "w_split", "rw_split", "ack_merge", 
                           "rack_merge", "rreq_split", "wreq_split","wack_merge"]
        ctrl_pos= [self.ctrl_split_ary_inst.get_pin("Q[0]").uc(),
                   self.ctrl_split_ary_inst.get_pin("Q[1]").uc(),
                   self.ctrl_split_ary_inst.get_pin("Q[2]").uc(),
                   self.ack_mrg_inst.get_pin("D[0]").uc(),
                   self.rack_mrg_inst.get_pin("D[0]").uc(),
                   self.ctrl_split_ary_inst.get_pin("Q[3]").uc(),
                   self.ctrl_split_ary_inst.get_pin("Q[4]").uc(),
                   self.wack_mrg_inst.get_pin("D[0]").uc()]
        
        for i in range(self.control_size):
            ctrl_split_y_off= self.reset_off.y- (i+1)*self.pitch
            ctrl_bus_pos= self.v_ctrl_bus_pos[control_pin_list[i]].bc()
            self.add_wire(self.m1_stack, [ctrl_pos[i]-vector(0, self.m2_width), (ctrl_pos[i].x,ctrl_split_y_off),
                          (ctrl_bus_pos[0],ctrl_split_y_off), ctrl_bus_pos]) 

    def route_split_cells_powers_and_selects(self):
        """ Connecting vdd, gnd, select and enables of split_merge_cells """
        
        power_select_pin= ["vdd", "gnd", "reset", "S"]
        for i in range(4):
            if self.orien == "H":
                x_off= self.bank_pos_1.x - self.bank.width
            if self.orien == "V":
                x_off= self.sp_mrg_ctrl_inst.lx()

            y_off=self.addr_split_ary_inst.by()
            width =self.bank_pos_0.x + self.bank.width - x_off

            self.add_rect(layer= "metal1",
                          offset=vector(x_off, y_off-(i+1)*self.pitch),
                          width= width,
                          height= self.m1_width)
            if (power_select_pin[i] != "vdd" and power_select_pin[i] != "gnd"):
                self.add_layout_pin(text=power_select_pin[i],
                                    layer= "metal1",
                                    offset=vector(x_off, y_off-(i+1)*self.pitch),
                                    width= self.m1_width,
                                    height= self.m1_width)

        if self.power_gate:
            offset = vector(x_off, y_off-5*self.pitch)
            self.add_rect(layer= "metal1",
                          offset=offset,
                          width= width,
                          height= self.m1_width)
            self.add_layout_pin(text="sleep",
                                layer= "metal1",
                                offset=offset,
                                width= self.m1_width,
                                height= self.m1_width)
                                
            pos1 = self.v_ctrl_bus_pos["sleep"].bc()
            pos2 = vector(self.v_bus_off.x-10*self.pitch+0.5*self.m2_width, pos1.y)
            pos3 = vector(pos2.x, offset.y+0.5*self.m1_width)
            pos4 = vector(pos2.x+0.5*width, pos3.y)
            self.add_wire(self.m1_stack, [pos1, pos2, pos3, pos4])
            self.add_via_center(self.m1_stack, pos1, rotate=90)
            #self.add_via_center(self.m1_stack, pos3+vector(0, 0.5*contact.m1m2.width), rotate=90)
        
        mod_list0=[self.dsplit_ary_inst, self.dmerge_ary_inst]
        mod_list1=[self.dsplit_ary_inst, self.addr_split_ary_inst, self.ctrl_split_ary_inst]
        mod_list2=[self.ack_mrg_inst, self.rack_mrg_inst, self.wack_mrg_inst]
        
        for i in range(3):
            for mod in (mod_list1 + mod_list2):
                power_pos= mod.get_pin(power_select_pin[i])
                self.add_wire(self.m1_stack,[power_pos.lc(), 
                              (power_pos.lx()-(1+i)*self.pitch, power_pos.lc().y), 
                              (power_pos.lx()-(1+i)*self.pitch, y_off-(i+1)*self.pitch)])
                self.add_via(self.m1_stack,(power_pos.lx()-(1+i)*self.pitch-\
                                            0.5*self.m2_width,y_off-(i+1)*self.pitch)) 

        for mod in mod_list1:
            select_pos= mod.get_pin("S")
            self.add_wire(self.m1_stack, [select_pos.lc(),
                          (select_pos.lx()-4*self.pitch, select_pos.lc().y), 
                          (select_pos.lx()-4*self.pitch, y_off-4*self.pitch)])
            self.add_via(self.m1_stack, (select_pos.lx()-4*self.pitch-0.5*self.m2_width,
                                         y_off-4*self.pitch)) 

        for mod in mod_list2:
            select_pos= mod.get_pin("M")
            self.add_wire(self.m1_stack, [select_pos.lc(),(select_pos.lx()-4*self.pitch, select_pos.lc().y), 
                          (select_pos.lx()-4*self.pitch,y_off-4*self.pitch)])
            self.add_via(self.m1_stack, (select_pos.lx()-4*self.pitch-0.5*self.m2_width,
                                         y_off-4*self.pitch)) 


        select_pin_S= ["en1_S", "en2_S"]
        select_split_pin_name=["rw_en1_S", "rw_en2_S"] 
        mod_list4=self.ctrl_split_ary_inst

        for i in range(2):
            pos1=mod_list4.get_pin(select_pin_S[i])
            pos2=vector(pos1.lx()-(i+5)*self.pitch, pos1.lc().y)
            pos3=vector(pos2.x, self.ctrl_split_ary_inst.by()-6*self.pitch)
            pos4=pos3-vector(0.5*self.m2_width, 0)
            self.add_wire(self.m1_stack, [pos1.lc(), pos2, pos3])
            self.add_layout_pin(text=select_split_pin_name[i],
                                layer= "metal2",
                                offset=pos4,
                                width= self.m2_width,
                                height= self.m2_width)

        select_merge_pin_name=["Mack_S", "Mrack_S", "Mwack_S"]
        for mod in mod_list2:
            pos1= mod.get_pin("en1_M")
            pos2=vector(pos1.lx()-5*self.pitch, pos1.lc().y)
            pos3=vector(pos2.x, self.ctrl_split_ary_inst.by()-8*self.pitch)
            pos4=pos3 - vector(0.5*self.m2_width, 0)
            self.add_wire(self.m1_stack, [pos1.lc(), pos2, pos3])
            self.add_layout_pin(text=select_merge_pin_name[mod_list2.index(mod)],
                                layer= "metal2",
                                offset=pos4,
                                width= self.m2_width,
                                height= self.m2_width)
           
        en2_merge=["rreq_split", "wreq_split"]
        mod_list=[self.rack_mrg_inst, self.wack_mrg_inst]
        for mod in mod_list:           
            pos1=mod.get_pin("en2_M")
            pos2=vector(pos1.lx()-6*self.pitch, pos1.lc().y)
            pos3=vector(pos2.x, self.reset_off.y- (6+mod_list.index(mod))*self.pitch)
            ctrl_pos= self.ctrl_split_ary_inst.get_pin("Q[{0}]".format(3+mod_list.index(mod))).uc()
            pos4=vector(ctrl_pos.x, pos3.y)
            self.add_wire(self.m1_stack, [pos1.lc(),pos2, pos3, pos4])

        ctrl_bus_pos= self.v_ctrl_bus_pos["rw_merge"].bc()
        pos1=self.ack_mrg_inst.get_pin("en2_M").lc()
        pos2=vector(pos1.x-6*self.pitch, pos1.y)
        pos3=vector(pos2.x, self.reset_off.y- 9*self.pitch)
        pos4=vector(ctrl_bus_pos[0], pos3.y)
        self.add_wire(self.m1_stack, [pos1, pos2, pos3, pos4, ctrl_bus_pos]) 

        power_select_pins= ["vdd", "gnd", "reset", "M"]
        for i in range(4):
            select_pos= self.dmerge_ary_inst.get_pin(power_select_pins[i])
            
            if self.orien == "H":
                y_off= self.dmerge_ary_inst.by()
                self.add_wire(self.m1_stack, [select_pos.lc(), 
                              (self.dmerge_ary_inst.rx()+(1+i)*self.pitch, 
                                select_pos.lc().y), 
                              (self.dmerge_ary_inst.rx()+(1+i)*self.pitch, 
                                y_off-(1+i)*self.pitch)])
                self.add_via(self.m1_stack, 
                            (select_pos.lx()+self.dmerge_ary.width+(1+i)*self.pitch-\
                            0.5*self.m2_width,y_off-(1+i)*self.pitch)) 
            
            if self.orien == "V":
                x_off =self.din1_bus_pos["din_split[0]"].lx()+self.data_bus_width
                y_off= self.dsplit_ary_inst.by()
                if self.mask:
                    index = 1+i+2*self.w_size
                else:
                    index =  1+i+self.w_size
                self.add_wire(self.m1_stack, [select_pos.lc(), 
                              (x_off+index*self.pitch, select_pos.lc().y), 
                              (x_off+index*self.pitch,  y_off-(1+i)*self.pitch),
                              (select_pos.lx(), y_off-(1+i)*self.pitch+0.5*self.m1_width)])

        
        #Connecting "vdd" & "gnd" and "reset" betweex_offn banks and ctrl_split arrays
        power_pins= ["vdd", "gnd"]
        for i in range(2):
            bank_power= self.sp_mrg_ctrl_inst.get_pin(power_pins[i])
            spl_mrg_power= self.addr_split_ary_inst.get_pin(power_pins[i])
            
            self.add_wire(self.m1_stack, [(spl_mrg_power.lx(), spl_mrg_power.lc().y),
                         (spl_mrg_power.lx()-(i+8)*self.pitch, spl_mrg_power.lc().y),
                         (spl_mrg_power.lx(), self.reset_off.y-(2-i)*self.pitch),
                         (bank_power.uc().x+0.5*self.m2_width, self.reset_off.y-(2-i)*self.pitch),
                         (bank_power.uc().x+0.5*self.m2_width, self.reset_off.y+self.m2_width)])

        
        # Connection S pin of split_merge_ctrl to select pin
        sel_pos0= self.v_ctrl_bus_pos["S"].bc()
        sel_pos1= vector(sel_pos0.x, sel_pos0.y-self.pitch)
        sel_pos2=vector(self.reset_off.x-9*self.pitch-0.5*self.m2_width, sel_pos1.y)
        sel_pos3=vector(sel_pos2.x, self.addr_split_ary_inst.by()-4*self.pitch)
        self.add_wire(self.m2_rev_stack, [sel_pos0, sel_pos1, sel_pos2, sel_pos3])
        self.add_via_center(self.m1_stack, sel_pos3)
        self.add_via_center(self.m2_stack, sel_pos1, rotate=90)
        
        spl_mrg_reset= self.addr_split_ary_inst.get_pin("reset")
        self.add_wire(self.m1_stack, [(spl_mrg_reset.lx(), spl_mrg_reset.lc().y),
                     (spl_mrg_reset.lx()-3*self.pitch, spl_mrg_reset.lc().y),
                     (spl_mrg_reset.lx()-3*self.pitch,self.reset_off.y-3*self.pitch),
                     (self.reset_off.x+0.5*self.m2_width, self.reset_off.y-3*self.pitch),
                     (self.reset_off.x+0.5*self.m2_width, self.reset_off.y+self.pitch)])

        spl_mrg_ack_merge= self.v_ctrl_bus_pos["ack_merge"].bc()
        self.add_wire(self.m1_stack, [(spl_mrg_ack_merge.x, spl_mrg_ack_merge.y),
                     (spl_mrg_ack_merge.x, self.reset_off.y-4*self.pitch),
                     (self.reset_off.x-6*self.pitch, self.reset_off.y-4*self.pitch),
                     (self.reset_off.x-6*self.pitch, 
                      self.ctrl_split_ary_inst.by()-8*self.pitch)])

        self.add_layout_pin(text="ack_merge",
                            layer= "metal2",
                            offset=(self.reset_off.x-6*self.pitch-0.5*self.m2_width, 
                                    self.ctrl_split_ary_inst.by()-8*self.pitch),
                            width= self.m2_width,
                            height= self.m2_width)
        
        #Connecting "rw_en1_sel" & "rw_en2_sel" between datain_spli, addr_spli and rwrw_split arrays
        select_pin_S= ["en1_S", "en2_S"]
        for i in range(2):
            en_data= self.dsplit_ary_inst.get_pin(select_pin_S[i])
            en_addr= self.addr_split_ary_inst.get_pin(select_pin_S[i])
            en_ctrl= self.ctrl_split_ary_inst.get_pin(select_pin_S[i])
            yoff= self.ctrl_split_ary_inst.by()-(6+i)*self.pitch
            self.add_wire(self.m1_stack,
                          [en_addr.lc(), (en_addr.lx()-(i+5)*self.pitch, en_addr.lc().y), 
                          (en_addr.lx()-(i+5)*self.pitch, yoff), 
                          (en_data.lx()-(i+5)*self.pitch, yoff),
                          (en_data.lx()-(i+5)*self.pitch, en_data.lc().y), en_data.lc()])

            self.add_wire(self.m1_stack,
                          [en_addr.lc(), (en_addr.lx()-(i+5)*self.pitch, en_addr.lc().y), 
                          (en_addr.lx()-(i+5)*self.pitch, yoff), 
                          (en_ctrl.lx()-(i+5)*self.pitch, yoff),
                          (en_ctrl.lx()-(i+5)*self.pitch, en_ctrl.lc().y), en_ctrl.lc()])

        #Connecting "rack_merge" of dataout_merge
        en_data= self.dmerge_ary_inst.get_pin("en1_M")
        en_ctrl= self.rack_mrg_inst.get_pin("D[0]")
        yoff= self.ctrl_split_ary_inst.by()-8*self.pitch
        if self.orien == "H":
            self.add_wire(self.m1_stack,
                          [en_ctrl.uc(), (self.rack_mrg_inst.lx()-7*self.pitch, en_ctrl.lc().y), 
                          (self.rack_mrg_inst.lx()-7*self.pitch, yoff), 
                          (self.dmerge_ary_inst.rx()+5*self.pitch, yoff),
                          (self.dmerge_ary_inst.rx()+5*self.pitch, en_data.lc().y), 
                           en_data.lc()])

        if self.orien == "V":
            x_off =self.din1_bus_pos["din_split[0]"].lx()+self.data_bus_width
            if self.mask:
                index=5+2*self.w_size
            else:
                index=5+self.w_size
            self.add_wire(self.m1_stack,
                          [en_ctrl.uc(), (self.rack_mrg_inst.lx()-7*self.pitch, en_ctrl.lc().y), 
                          (self.rack_mrg_inst.lx()-7*self.pitch, yoff), 
                          (x_off+index*self.pitch, yoff),
                          (x_off+index*self.pitch, 
                           en_data.lc().y), en_data.lc()])

        #Connecting "Mdout" of dataout_merge
        en_data= self.dmerge_ary_inst.get_pin("en2_M")
        yoff= self.ctrl_split_ary_inst.by()-8*self.pitch
        if self.orien == "H":
            self.add_wire(self.m1_stack,
                          [(self.dmerge_ary_inst.rx()+6*self.pitch, yoff),
                          (self.dmerge_ary_inst.rx()+6*self.pitch, en_data.lc().y), 
                           en_data.lc()])


            Mdout_off = (self.dmerge_ary_inst.rx()+6*self.pitch-0.5*self.m2_width, yoff)
        if self.orien == "V":
            if self.mask:
                index=6+2*self.w_size
            else:
                index=6+self.w_size
            self.add_wire(self.m1_stack,
                          [(x_off+index*self.pitch, yoff),
                          (x_off+index*self.pitch, 
                           en_data.lc().y), en_data.lc()])
            Mdout_off = (x_off+index*self.pitch-0.5*self.m2_width, yoff)

        self.add_layout_pin(text="Mdout", 
                            layer="metal2", 
                            offset= Mdout_off,
                            width=self.m2_width, 
                            height=self.m2_width)
