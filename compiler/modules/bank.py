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
from tech import drc, parameter, info
import debug
import design
import math
from math import log,sqrt,ceil
import contact
from vector import vector
from utils import ceil as util_ceil
from data_ready import data_ready

class bank(design.design):
    """ Dynamically generate a single asynchronous bank with ctrl logic"""

    def __init__(self, word_size, words_per_row, num_rows, num_subanks, two_level_bank, mask, power_gate, name="bank"):

        mod_list = ["bitcell", "bitcell_array", "precharge_array", "column_mux_array", 
                    "sense_amp_array", "write_driver_array", "write_complete_array", 
                    "hierarchical_decoder", "wordline_driver_array", "single_driver_array", 
                     "driver", "split_array", "merge_array","bank_control_logic", "pinv"]
        for mod_name in mod_list:
            class_file = reload(__import__(mod_name))
            mod_class = getattr(class_file, mod_name)
            setattr (self, mod_name, mod_class)

        design.design.__init__(self, name)
        self.w_size = word_size
        self.w_per_row = words_per_row
        self.num_rows = num_rows
        self.num_subanks = num_subanks
        self.two_level_bank = two_level_bank
        self.mask = mask
        self.power_gate = power_gate
        
        self.compute_sizes()
        self.add_pins()
        self.create_modules()
        self.add_modules()
        self.route_layout()
        self.offset_all_coordinates()
        self.ctrl_shift = self.ctrl_logic_inst.get_pin("reset").lx()-4*self.m_pitch("m1")
        if self.power_gate:
            self.ctrl_shift-=5*self.m_pitch("m1")

    def compute_sizes(self):
        """  Computes the required sizes and spaces to create the bank """

        self.num_bls = self.w_per_row*self.w_size
        self.row_addr_size = int(log(self.num_rows, 2))
        self.subank_addr_size = int(log(self.num_subanks, 2))
        self.mux_addr_size = int(log(self.w_per_row, 2))
        self.addr_size = self.subank_addr_size + self.row_addr_size + self.mux_addr_size
        
        #This is the extra space needed to ensure DRC rules to the m1/m2 contacts
        self.m1m2_m2m3_fix = contact.m2m3.width - contact.m1m2.width

        # Width for vdd & gnd rail
        self.pow_width = 2*self.m_pitch("m1")
        
        via_pitch = drc["minwidth_via1"]+drc["via1_to_via1"]
        self.num_via = int(ceil((self.pow_width+drc["via1_to_via1"]-2*drc["metal1_extend_via1"]) / via_pitch))
        via1=contact.contact(layer_stack=("metal1", "via1", "metal2"), dimensions=[1,self.num_via])
        via2=contact.contact(layer_stack=("metal2", "via2", "metal3"), dimensions=[1,self.num_via])
        self.pow_width = max(via1.height, via2.height)
        self.pow_pitch = self.pow_width + self.m_pitch("m1")
        
        if self.two_level_bank:
            self.go_name="go_s[{0}]"
            self.addr_name = "addr_split[{0}]"
            self.din_name = "din_split[{0}][{1}]"
            self.bm_name = "bm_split[{0}][{1}]"
            self.dout_name = "dout_merge[{0}][{1}]"
            self.dout_bar_name = "dout_bar_merge[{0}][{1}]"
        else:
            self.go_name="go[{0}]"
            self.addr_name = "addr[{0}]"
            self.din_name = "din[{0}][{1}]"
            self.bm_name = "bm[{0}][{1}]"
            self.dout_name = "dout[{0}][{1}]"
            self.dout_bar_name = "dout_bar[{0}][{1}]"
        
        # Data_out and data_out_bar of first s_amp in each sub-bank are used 
        # to create data_ready signal for that sub-bank
        self.data_ready_size = self.num_subanks
        
        # BL and BR of first bitcell of each word in each sub-bank are used
        # to create w_complete signal for that sub-bank.
        self.write_comp_size = self.num_subanks
        
        # ctrl lines (pchg, sen, wen) to ctrl modules in array
        self.num_ctrl_lines = 3 

        # ctrl lines(reset, S, en1, en2) for split and merge
        if self.two_level_bank:
            self.num_split_ctrl_lines = 4
        
        # Bus_size for read-complete and write-complete signals +  one space on each side
        self.comp_bus_width=(2 + self.data_ready_size + self.write_comp_size)*self.m_pitch("m2")

        # This is the ctrl bus to route pchg, sen, wen and col_mux_sel to each column
        self.ctrl_bus_width=2*self.pow_pitch+self.m_pitch("m2")*(self.num_ctrl_lines+2)
        if self.w_per_row > 1: 
            self.ctrl_bus_width=self.ctrl_bus_width+self.m_pitch("m2")*self.w_per_row
        
        # This is the space between col_mux_drv and col_mux_array
        self.ctrl_go_width=2*self.m_pitch("m2")
        
        if self.num_subanks > 1:
            self.ctrl_go_width=4*self.m_pitch("m2")
            if self.w_per_row > 1:
                self.ctrl_go_width=(self.w_per_row+3)*self.m_pitch("m2")
       
            if self.two_level_bank:
                self.ctrl_go_width=(self.w_per_row+13)*self.m_pitch("m2")
        if self.mask: 
            self.ctrl_go_width = self.ctrl_go_width + self.m_pitch("m2")
    
    def add_pins(self):
        """ Add DATA, ADDR and ctrl pins for bank module """
        
        for i in range(self.num_subanks):
            for j in range(self.w_size):
                self.add_pin("din[{0}][{1}]".format(i, j))
        for i in range(self.num_subanks):
            for j in range(self.w_size):
                self.add_pin("dout[{0}][{1}]".format(i, j))
        for i in range(self.addr_size):
            self.add_pin("addr[{0}]".format(i))
        if self.mask:
            for i in range(self.num_subanks):
                for j in range(self.w_size):
                    self.add_pin("bm[{0}][{1}]".format(i, j))

        self.add_pin_list(["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"])
        
        # ADD ctrl pins for split and merge cells
        if self.two_level_bank:
            self.add_pin_list(["S","ack_merge","rw_en1_S","rw_en2_S","Mack","Mrack","Mwack", "Mdout"]) 
        if self.power_gate:
            self.add_pin("sleep")

        self.add_pin("vdd")
        self.add_pin("gnd")
       
    def add_modules(self):
        """ Add all the banks' submodules in the following order"""

        self.add_bitcell_array()
        self.add_pchg_array()
        if self.mux_addr_size > 0:
            self.add_col_mux_height=self.mux_array.height
            self.add_col_mux_array()
        else:
            self.add_col_mux_height=1.5*self.well_space
        self.add_s_amp_array()
        self.add_data_ready()
        self.add_w_drv_array()
        self.add_w_complete()
        if self.two_level_bank:
            self.add_din_split_array()
            self.add_dout_merge_array()
        self.add_row_dec()
        if self.mux_addr_size > 0: 
            self.add_col_mux_dec()
        if self.subank_addr_size > 0: 
            self.add_subank_dec()
        else:
            self.subank_dec_drv_height=0
        if self.two_level_bank:
            self.add_addr_split_ary()
            self.add_ctrl_merge_cells()
            self.add_ctrl_split_ary()
        
        if self.subank_addr_size > 0:
            self.add_go_drv() 
        
        self.add_ctrl_logic()

    def create_modules(self):
        """ Create all the submodules using the class loader """
        
        self.bitcell = self.bitcell()
        self.add_mod(self.bitcell)
        
        self.bitcell_array = self.bitcell_array(cols=self.num_bls, 
                                                rows=self.num_rows, 
                                                name="bitcell_ary")
        self.add_mod(self.bitcell_array)

        self.pchg_array = self.precharge_array(columns=self.num_bls, name="pchg_ary")
        self.add_mod(self.pchg_array)

        if self.mux_addr_size > 0:
            self.mux_array = self.column_mux_array(columns=self.num_bls, 
                                                   word_size=self.w_size, 
                                                   name="col_mux_ary")
            self.add_mod(self.mux_array)
                
        self.s_amp_array = self.sense_amp_array(word_size=self.w_size, 
                                                words_per_row=self.w_per_row, 
                                                name="s_amp_ary")
        self.add_mod(self.s_amp_array)
        
        self.w_drv_array = self.write_driver_array(word_size=self.w_size, 
                                                   words_per_row=self.w_per_row,  
                                                   mask= self.mask, 
                                                   name="w_drv_ary")
        self.add_mod(self.w_drv_array)

        self.row_dec = self.hierarchical_decoder(rows=self.num_rows)
        self.add_mod(self.row_dec)

        if self.num_subanks > 1:
            self.bitcell_array_drv = self.single_driver_array(rows=self.num_rows, 
                                                              name="bitcell_ary_drv")
            self.add_mod(self.bitcell_array_drv)

            self.pchg_drv = self.driver(rows=1, inv_size=10, name="pchg_drv")
            self.add_mod(self.pchg_drv)
        
            self.go_size = 2
            if self.two_level_bank:
                self.go_size = self.go_size + 6
            if self.w_per_row > 1:
                self.go_size = self.go_size + self.w_per_row
            
            self.go_drv = self.driver(rows=self.go_size, inv_size=10, name="go_drv")
            self.add_mod(self.go_drv)
        
        self.row_dec_drv = self.wordline_driver_array(rows=self.num_rows, name="row_dec_drv")
        self.add_mod(self.row_dec_drv)
        

        self.subank_dec_drv = self.driver(rows=self.num_subanks, inv_size=1, name="col_dec_drv")
        self.add_mod(self.subank_dec_drv)

        if self.two_level_bank:
            self.subank_dec_drv2 = self.driver(rows=self.num_subanks, inv_size=10, name="col_dec_drv2")
            self.add_mod(self.subank_dec_drv2)

        if self.two_level_bank:
            self.d_split_array = self.split_array(name="d_split_ary", 
                                                  word_size=self.w_size,
                                                  mask= self.mask, 
                                                  words_per_row=self.w_per_row)
            self.add_mod(self.d_split_array)

            self.d_merge_array = self.merge_array(name="d_merge_ary", 
                                                  word_size=self.w_size, 
                                                  words_per_row=self.w_per_row)
            self.add_mod(self.d_merge_array)
        
            self.addr_split_array = self.split_array(name="addr_split_ary", 
                                                    word_size=self.addr_size, 
                                                    mask = False, words_per_row=1)
            self.add_mod(self.addr_split_array)

            self.ctrl_split_array = self.split_array(name="ctrl_split_ary", 
                                                     word_size=5, mask = False, 
                                                     words_per_row=1)
            self.add_mod(self.ctrl_split_array)

            self.ctrl_merge_cell = self.merge_array(name="ctrl_merge_cell", 
                                                    word_size=1, words_per_row=1)
            self.add_mod(self.ctrl_merge_cell)

        self.inv = self.pinv(size = 1)
        self.add_mod(self.inv)

        self.w_complete = self.write_complete_array(columns=self.num_bls, 
                                                    word_size=self.w_size, 
                                                    name="w_complete")
        self.add_mod(self.w_complete)
        
        self.data_ready = data_ready()
        self.add_mod(self.data_ready)

        self.ctrl_logic = self.bank_control_logic(num_rows=self.num_rows, 
                                                  num_subanks=self.num_subanks, 
                                                  two_level_bank=self.two_level_bank,
                                                  power_gate = self.power_gate)
        self.add_mod(self.ctrl_logic)
        
    def route_layout(self):
        """ Create routing amoung the modules"""
        
        self.add_power_lines()
        self.route_go_drv()
        self.add_ctrl_bus()
        self.add_data_ready_bus()
        self.add_w_complete_bus()
        self.add_and_route_address_bus()
        self.add_col_mux_sel_routing()
        if self.num_subanks > 1:
            self.go_signal_routing()
        if self.two_level_bank:
            self.route_split_merge_data()
        else:
            self.route_data_in_and_data_out()
        self.route_ctrl_logic()
        if self.two_level_bank:
            self.route_split_merge_to_ctrl_logic()
            self.route_ctrl_split_merge_cells()
        if self.mask:
            self.route_bm_write_comp()
        self.route_power()

    def add_bitcell_array(self):
        """ Add bitcell array and bitcell_driver (WL is Anded with go signal) """

        # Total width of each sub-bank and  X-Ofsset of bitcell_array in sub-bank
        if self.num_subanks == 1:
            #extra space for max width of write_complete or data_ready (nand2)
            self.bitcell_ary_off=max(self.data_ready.width+self.ctrl_bus_width+self.ctrl_go_width, 
                                     self.w_complete.wc_x_shift+self.ctrl_bus_width-2*self.pow_pitch)
        else:
            if info["foundry_cell"]:
                self.ctrl_go_width = self.ctrl_go_width - self.bitcell_array.xleft_shift

            #extra space for write_complete or go signal driver (pchg_drv)
            self.bitcell_ary_off=max(max(self.pchg_drv.width, self.bitcell_array_drv.width)+\
                                     self.ctrl_bus_width+self.ctrl_go_width, 
                                     self.w_complete.wc_x_shift+self.ctrl_bus_width-2*self.pow_pitch)
        
        self.subank_width= self.bitcell_ary_off+self.bitcell_array.width+2*self.pow_pitch+self.m_pitch("m1")

        self.cell_ary_inst={}
        self.bitcell_ary_drv_inst={}
        for i in range(self.num_subanks):
            x_offset=i*self.subank_width + self.bitcell_ary_off
            offset=vector(x_offset,-self.bitcell_array.y_shift)
            self.cell_ary_inst[i]=self.add_inst(name="bitcell_ary_{0}".format(i), 
                                                mod=self.bitcell_array, 
                                                offset=offset)
            temp = []
            if self.num_subanks == 1:
                for j in range(self.num_bls):
                    temp.extend(["bl[{0}]".format(j),"br[{0}]".format(j)])
                for j in range(self.num_rows):
                    temp.append("gwl[{0}]".format(j))
            if self.num_subanks > 1:
                for j in range(self.num_bls):
                    temp.extend(["bl[{0}][{1}]".format(i,j),"br[{0}][{1}]".format(i,j)])
                for j in range(self.num_rows):
                    temp.append("wl[{0}][{1}]".format(i,j))
            temp.extend(["vdd", "gnd"])
            self.connect_inst(temp)

            x_offset=i*self.subank_width+ self.ctrl_bus_width 
            if self.two_level_bank:
                x_offset = x_offset + 3*self.m_pitch("m1") 
            if self.num_subanks > 1:   
                self.bitcell_ary_drv_inst[i] = self.add_inst(name="bitcell_drv_{0}".format(i), 
                                                             mod=self.bitcell_array_drv, 
                                                             offset=vector(x_offset,0))
                temp = []
                for j in range(self.num_rows):
                    temp.append("gwl[{0}]".format(j))
                for j in range(self.num_rows):
                    temp.append("wl[{0}][{1}]".format(i,j))
                temp.extend([self.go_name.format(i), "vdd", "gnd"])
                self.connect_inst(temp)

                # Connecting output of bitcell_array drv (wordline drv) to WL in bitcell array
                for k in range(self.num_rows):
                    bit_ary_drv_out = self.bitcell_ary_drv_inst[i].get_pin("out[{0}]".format(k))
                    bitcell_wl = self.cell_ary_inst[i].get_pin("wl[{0}]".format(k))
                    
                    if bitcell_wl.layer=="metal1":
                        layer ="metal1"
                    else:
                        layer ="metal3"
                    
                    self.add_path(layer, [bit_ary_drv_out.lc(), bitcell_wl.lc()])

    def add_pchg_array(self):
        """ Add precharge array and precharge driver (pchg is Anded with go signal) """ 

        y_offset=self.cell_ary_inst[0].uy()
        self.pchg_ary_inst={}
        self.pchg_drv_inst={}
        for i in range(self.num_subanks):
            x_offset=self.subank_width * i + self.bitcell_ary_off + self.bitcell_array.xleft_shift
            self.pchg_ary_inst[i]=self.add_inst(name="pchg_ary{0}".format(i), 
                                                mod=self.pchg_array, 
                                                offset=vector(x_offset,y_offset))
            temp = []
            if self.num_subanks == 1:
                for j in range(self.num_bls):
                    temp.extend(["bl[{0}]".format(j),"br[{0}]".format(j)])
                temp.extend(["pchg", "vdd"])
            if self.num_subanks > 1:
                for j in range(self.num_bls):
                    temp.extend(["bl[{0}][{1}]".format(i,j), "br[{0}][{1}]".format(i,j)])
                temp.extend(["pchg[{0}]".format(i), "vdd"])
            self.connect_inst(temp)
            
            if self.num_subanks > 1:
                offset= vector(self.bitcell_ary_drv_inst[i].lx(), y_offset)
                self.pchg_drv_inst[i]=self.add_inst(name="pchg_drv_{0}".format(i), 
                                                    mod=self.pchg_drv, 
                                                    offset=offset)
                temp=["pchg","pchg[{0}]".format(i), self.go_name.format(i),"vdd","gnd"]
                self.connect_inst(temp)

                # Connecting output of pchg_array drv to pchg[i] in precharge array
                pchg_drv_out = self.pchg_drv_inst[i].get_pin("out[0]").lc()
                precharge_en = self.pchg_ary_inst[i].get_pin("en").lc()
                mid_pos=(precharge_en.x-0.5*self.m_pitch("m1"), pchg_drv_out.y)
                self.add_wire(self.m1_stack, [pchg_drv_out,mid_pos,precharge_en])

    def add_col_mux_array(self):
        """ Add column-mux when words_per_row > 1 and its driver (sel[i] is Anded with go signal) """ 

        self.y_offset=self.add_col_mux_height + self.bitcell_array.ybot_shift
        self.mux_ary_inst={}
        for i in range(self.num_subanks):
            x_offset=self.subank_width * i + self.bitcell_ary_off + self.bitcell_array.xleft_shift
            offset= vector(x_offset, self.y_offset)
            self.mux_ary_inst[i]=self.add_inst(name="col_mux_ary{0}".format(i), 
                                               mod=self.mux_array,
                                               offset=offset.scale(1,-1))
            temp = []
            if self.num_subanks == 1:
                for j in range(self.num_bls):
                    temp.extend(["bl[{0}]".format(j), "br[{0}]".format(j)])
                if self.w_per_row ==4:
                    for k in range(self.w_per_row):
                        temp.append("pre_sel[{0}]".format(k))
                if self.w_per_row ==2:
                    temp.extend(["pre_sel[1]", self.addr_name.format(self.row_addr_size)])
                for j in range(self.w_size):
                    temp.extend(["bl_out[{0}]".format(j),"br_out[{0}]".format(j)])
            
            if self.num_subanks > 1:
                for j in range(self.num_bls):
                    temp.extend(["bl[{0}][{1}]".format(i,j),"br[{0}][{1}]".format(i,j)])
                for k in range(self.w_per_row):
                    temp.append("sel[{0}][{1}]".format(i,self.w_per_row-1-k))
                for j in range(self.w_size):
                    temp.extend(["bl_out[{0}][{1}]".format(i,j), "br_out[{0}][{1}]".format(i,j)])
            temp.append("gnd")
            self.connect_inst(temp)

    def add_go_drv(self):
        """ Add go signal driver for ctrl signals"""
        
        self.go_drv_inst={}
        for i in range(self.num_subanks):
            xoff=self.bitcell_ary_drv_inst[i].lx()
            yoff=self.w_drv_ary_inst[0].get_pin("en").by()
            offset= vector(xoff,yoff)
            self.go_drv_inst[i]=self.add_inst(name="go_drv_{0}".format(i), 
                                              mod=self.go_drv,
                                              offset=offset,
                                              mirror="MX")
            temp = []
            if self.w_per_row ==4:
                for k in range(self.w_per_row):
                    temp.append("pre_sel[{0}]".format(k))
            if self.w_per_row ==2:
                temp.extend(["pre_sel[1]", self.addr_name.format(self.row_addr_size)])
            temp.extend(["sen", "wen"])
            
            if self.two_level_bank:
                temp.extend(["rw_en1_S", "rw_en2_S", "vdd"])
                temp.extend(["rack_merge", "Mdout", "vdd"])
            
            if self.w_per_row > 1:
                for k in range(self.w_per_row):
                    temp.append("sel[{0}][{1}]".format(i,k))
            
            temp.extend(["sen[{0}]".format(i), "wen[{0}]".format(i)])
            
            if self.two_level_bank:
                temp.extend(["rw_en1_S[{0}]".format(i), "rw_en2_S[{0}]".format(i), "go_sx[{0}]".format(i)])
                temp.extend(["Mrack[{0}]".format(i), "rreq_merge[{0}]".format(i), "go_mx[{0}]".format(i)])
                temp.extend([self.go_name.format(i),"vdd","gnd"])
            else:
                temp.extend([self.go_name.format(i),"vdd","gnd"])
            self.connect_inst(temp)

    def route_go_drv(self):
        """ route input and output of go driver array"""

        self.split_xoffset={}
        self.merge_xoffset={}

        if (self.num_subanks ==1 and self.two_level_bank):
            #en2_M
            self.merge_xoffset[0]=self.d_split_ary_inst[0].lx()-self.m_pitch("m2")
            #en1_M
            self.merge_xoffset[1]=self.merge_xoffset[0]-self.m_pitch("m2")        
            #en2_s
            self.split_xoffset[0]=self.merge_xoffset[1]-self.m_pitch("m2")
            #en1_s
            self.split_xoffset[1]=self.split_xoffset[0]-self.m_pitch("m2")
            #reset
            self.split_xoffset[2]=self.split_xoffset[1]-self.m_pitch("m2")
            #S/M
            self.split_xoffset[3]=self.split_xoffset[2]-self.m_pitch("m2")
        
        if self.num_subanks > 1:
            if self.w_per_row>1:
                index = self.w_per_row
                shift = 0
            else:
                index = 0
                shift = self.m2_width
                
            for i in range(self.num_subanks):
                # Connecting output of go driver to ctrl in of sub_arrays
                if self.w_per_row > 1:
                    for k in range(self.w_per_row):
                        en = self.mux_ary_inst[i].get_pin("sel[{0}]".format(self.w_per_row-1-k)).lc()
                        out = self.go_drv_inst[i].get_pin("out[{0}]".format(k))
                        mid_pos1 = vector(out.rx()+(k+1)*self.m_pitch("m1"), out.lc().y)
                        mid_pos2 = vector(mid_pos1.x, en.y)
                        self.add_wire(self.m1_stack, [out.lc(), mid_pos1, mid_pos2, en])
            
                mod=[self.w_drv_ary_inst[i], self.s_amp_ary_inst[i]]
                for j in range(2):
                
                    en = mod[j].get_pin("en").lc()
                    out = self.go_drv_inst[i].get_pin("out[{0}]".format(index+1-j))
                    mid_pos1 = vector(out.rx()+(index+j+1)*self.m_pitch("m1")+0.5*self.m1_space, out.lc().y)
                    mid_pos2 = vector(mid_pos1.x, en.y)
                    self.add_wire(self.m1_stack, [out.lc(), mid_pos1, mid_pos2, en])
                
                    inp = self.go_drv_inst[i].get_pin("in[{0}]".format(index+j)).lc()
                    xoff=i*self.subank_width+ (j+1)*self.m_pitch("m2")+self.m2_width
                    if self.w_per_row>1:
                        xoff=i*self.subank_width+(j+1+self.w_per_row)*self.m_pitch("m2")

                    pos=vector(xoff, inp.y)
                    self.add_path("metal1", [inp, pos])
                    self.add_via_center(self.m1_stack, pos)

              
                if self.two_level_bank:
                    y1=self.d_split_ary_inst[i].get_pin("en2_S").uy()
                    y2=self.d_split_ary_inst[i].get_pin("en1_S").uy()
                    y3=self.go_drv_inst[i].get_pin("out[{}]".format(index+2)).uy()
                    heightx=abs(self.d_merge_ary_inst[i].by()-max(y1, y2, y3))
                    yoff= min(self.d_merge_ary_inst[i].by(), self.go_drv_inst[i].by())
                    self.rail_Xindex=[]
                    shift = 0.5*(contact.m1m2.height-contact.m1m2.first_layer_height)
                    
                    # "en1_S", "en2_S", "S", "en1_M", "en2_M", "M"
                    for j in range(6):
                        xoffx=self.d_split_ary_inst[i].lx()-(2+j)*self.m_pitch("m2")-self.m2_space
                        if self.mask:
                            xoffx=xoffx-self.m_pitch("m2")
                        self.rail_Xindex.append(xoffx)
                        heightx = heightx 
                        self.add_rect(layer="metal2",
                                           offset=(xoffx, yoff),
                                           width=self.m2_width,
                                           height=heightx- 2*(j//3)*self.inv.height)
                    
                        pos= vector(self.go_drv_inst[i].rx(), self.go_drv_inst[i].get_pin("out[{0}]".format(index+2+j)).by())
                        self.add_via(self.m2_stack, pos-vector(0, shift))
                        self.add_via(self.m1_stack, pos-vector(0, shift))
                        height=util_ceil(self.m2_minarea/contact.m1m2.width)
                        self.add_rect(layer="metal2", offset=pos-vector(0, height), width=contact.m1m2.width, height=1.5*height)
                    
                    pin=["en1_S", "en2_S", "S"]
                    for j in range(3):
                        en = self.d_split_ary_inst[i].get_pin(pin[j]).lc()
                        out = self.go_drv_inst[i].get_pin("out[{0}]".format(j+index+2)).lc()
                        self.add_path("metal1",[en, (self.rail_Xindex[j], en.y)])
                        self.add_via_center(self.m1_stack, (self.rail_Xindex[j]+0.5*self.m2_width, en.y))
                        self.add_path("metal3",[out, (self.rail_Xindex[j],out.y)])
                        self.add_via_center(self.m2_stack, (self.rail_Xindex[j]+0.5*self.m2_width, out.y))

                    pin=["en1_M", "en2_M", "M"]
                    for j in range(3):
                        en = self.d_merge_ary_inst[i].get_pin(pin[j]).lc()
                        out = self.go_drv_inst[i].get_pin("out[{0}]".format(j+index+5)).lc()
                        self.add_path("metal1",[en, (self.rail_Xindex[j+3], en.y)])
                        self.add_via_center(self.m1_stack, (self.rail_Xindex[j+3]+0.5*self.m2_width, en.y))
                        self.add_path("metal3",[out, (self.rail_Xindex[j+3],out.y)])
                        self.add_via_center(self.m2_stack, (self.rail_Xindex[j+3]+0.5*self.m2_width, out.y))
                    
                    
                    for k in range(4):
                        pos1= self.go_drv_inst[i].get_pin("in[{0}]".format(index+6-k-(k//2))).lc()-vector(0.5*contact.m1m2.width, 0)
                        pos2=vector(pos1.x-(k+2)*self.m_pitch("m2"), pos1.y)+vector(0.5*contact.m1m2.width+0.5*self.m2_width, 0)
                        pos3=vector(pos2.x, self.min_point_y)
                        self.add_path("metal3", [pos1, pos2, pos3])
                        self.add_via_center(self.m2_stack, pos1, rotate=90)
                        self.add_via_center(self.m1_stack, pos1, rotate=90)
                        height=util_ceil(self.m2_minarea/contact.m1m2.height)
                        self.add_rect_center(layer="metal2", offset=pos1, width=contact.m1m2.height, height=2*height)

                    #reset
                    self.split_xoffset[2]=self.d_split_ary_inst[0].lx()-self.m_pitch("m2")
                    #en1_M
                    self.merge_xoffset[1]=self.go_drv_inst[0].get_pin("in[0]").lc().x-2*self.m_pitch("m2")+0.5*self.m2_width
                    #en2_M
                    self.merge_xoffset[0]=self.merge_xoffset[1] - self.m_pitch("m2")        
                    #en1_s
                    self.split_xoffset[1]=self.merge_xoffset[0] - self.m_pitch("m2")
                    #en2_s
                    self.split_xoffset[0]=self.split_xoffset[1] - self.m_pitch("m2")

    def add_s_amp_array(self):
        """ Add s_amp array and its drv (sen[i] is Anded with go signal) """

        self.y_offset=self.add_col_mux_height+ self.s_amp_array.height+ self.bitcell_array.ybot_shift
        self.s_amp_ary_inst={}
        for i in range(self.num_subanks):
            x_offset=self.subank_width * i + self.bitcell_ary_off + self.bitcell_array.xleft_shift
            offset=vector(x_offset,self.y_offset)
            self.s_amp_ary_inst[i]=self.add_inst(name="s_amp_ary_{0}".format(i),
                                                 mod=self.s_amp_array,
                                                 offset=offset.scale(1,-1))
            temp = []
            if self.num_subanks==1:
                for j in range(self.w_size):
                    temp.extend([self.dout_name.format(0,j),self.dout_bar_name.format(0,j)])

                    if self.w_per_row == 1:
                        temp.extend(["bl[{0}]".format(j),"br[{0}]".format(j)])
                    else:
                        temp.extend(["bl_out[{0}]".format(j),"br_out[{0}]".format(j)])
                    temp.extend(["dready[{0}][{1}]".format(i,j)])
                temp.extend(["sen", "vdd", "gnd"])
            
            if self.num_subanks>1:
                for j in range(self.w_size):
                    temp.extend([self.dout_name.format(i,j),self.dout_bar_name.format(i,j)])
                    if self.w_per_row == 1:
                        temp.extend(["bl[{0}][{1}]".format(i,j),"br[{0}][{1}]".format(i,j)])
                    else:
                        temp.extend(["bl_out[{0}][{1}]".format(i,j),"br_out[{0}][{1}]".format(i,j)])
                    temp.extend(["dready[{0}][{1}]".format(i,j)])
                temp.extend(["sen[{0}]".format(i), "vdd", "gnd"])
            self.connect_inst(temp)
            
            if self.w_per_row == 1:
                for j in range(self.w_size):
                    BC_BL = self.cell_ary_inst[i].get_pin("bl[{0}]".format(j)).bc()
                    BC_BR = self.cell_ary_inst[i].get_pin("br[{0}]".format(j)).bc()
                    SA_BL = self.s_amp_ary_inst[i].get_pin("bl[{0}]".format(j)).uc()
                    SA_BR = self.s_amp_ary_inst[i].get_pin("br[{0}]".format(j)).uc()
                    self.add_path("metal2", [BC_BL, SA_BL])
                    self.add_path("metal2", [BC_BR, SA_BR])

    def add_data_ready(self):
        """ Add 2-input nand gate to detect data_ready on dout and dout_bar for read completion """

        self.data_ready_inst={}
        for i in range(self.num_subanks):
            x_offset=i * self.subank_width + self.bitcell_ary_off
            offset=vector(x_offset-self.ctrl_go_width+self.m1_space-self.data_ready.width, self.y_offset+2*self.m_pitch("m1"))
            self.data_ready_inst[i]=self.add_inst(name="data_ready_{0}".format(i),
                                                  mod=self.data_ready,
                                                  offset=offset.scale(1,-1))
            temp = ["dready[{0}][0]".format(i),self.dout_bar_name.format(i,0)]
            temp.extend(["sen", "data_ready[{0}]".format(i),"vdd", "gnd"])
            self.connect_inst(temp)

            # Connecting dout of s_amp to input A and dout_bar of s_amp to input B of nand gate
            data_out = self.s_amp_ary_inst[i].get_pin("d[0]").uc()
            data_out_bar = self.s_amp_ary_inst[i].get_pin("data_bar[0]").uc()
            
            dr_in_A = self.data_ready_inst[i].get_pin("bl") 
            dr_in_B = self.data_ready_inst[i].get_pin("br") 
            
            self.add_path("metal1", [(data_out.x, dr_in_A.lc().y), dr_in_A.lc()])
            self.add_path("metal1", [(data_out_bar.x, dr_in_B.lc().y), dr_in_B.lc()])
            
            self.add_via(self.m1_stack, (data_out.x-0.5*self.m2_width, dr_in_A.by()-self.via_shift("v1")))
            self.add_via(self.m1_stack, (data_out_bar.x-0.5*self.m2_width, dr_in_B.by()-self.via_shift("v1")))
            self.add_path("metal2", [data_out, (data_out.x, dr_in_A.lc().y)])
            self.add_path("metal2", [data_out_bar, (data_out_bar.x, dr_in_B.lc().y)])

    def add_w_drv_array(self):
        """ Add w_drv and w_drv drv (wen[i] is Anded with go signal) """ 

        self.y_offset= self.y_offset+self.w_drv_array.height+ (self.num_subanks+2)*self.m_pitch("m1")
        self.w_drv_ary_inst={}
        for i in range(self.num_subanks):
            x_offset=self.subank_width * i + self.bitcell_ary_off + self.bitcell_array.xleft_shift
            offset= vector(x_offset,self.y_offset)
            self.w_drv_ary_inst[i]=self.add_inst(name="w_drv_array_[{0}]".format(i), 
                                                 mod=self.w_drv_array,
                                                 offset=offset.scale(1,-1))
            temp = []
            for j in range(self.w_size):
                temp.append(self.din_name.format(i,j))
                if self.mask:
                    temp.append(self.bm_name.format(i,j))
                else:
                    temp.append("vdd")

                if self.num_subanks ==1:
                    if (self.w_per_row == 1):            
                        temp.extend(["bl[{0}]".format(j), "br[{0}]".format(j)])
                    else:
                        temp.extend(["bl_out[{0}]".format(j), "br_out[{0}]".format(j)])
            
                if self.num_subanks > 1:
                    if (self.w_per_row == 1):            
                        temp.extend(["bl[{0}][{1}]".format(i,j),"br[{0}][{1}]".format(i,j)])
                    else:
                        temp.extend(["bl_out[{0}][{1}]".format(i,j),"br_out[{0}][{1}]".format(i,j)])
            if self.num_subanks ==1:
                temp.extend(["wen", "pchg", "vdd", "gnd"])
            else:
                temp.extend(["wen[{0}]".format(i), "pchg", "vdd", "gnd"])

            self.connect_inst(temp)

            #connect write_driver BL & BR to sense_amp BL &BR
            # bitlines cannot be connected just by abutment because of data ready nand2
            for j in range(0, self.w_per_row*self.w_size, self.w_per_row):
                WD_BL = self.w_drv_ary_inst[i].get_pin("bl[{0}]".format(j)).uc()
                WD_BR = self.w_drv_ary_inst[i].get_pin("br[{0}]".format(j)).uc()
                SA_BL = self.s_amp_ary_inst[i].get_pin("bl[{0}]".format(j)).uc()
                SA_BR = self.s_amp_ary_inst[i].get_pin("br[{0}]".format(j)).uc()
                self.add_path("metal2", [WD_BL, (WD_BL.x, self.s_amp_ary_inst[i].by())])
                self.add_path("metal2", [WD_BR, (WD_BR.x, self.s_amp_ary_inst[i].by())])
            
    def add_w_complete(self):
        """ Add write_complete to detect completion of write on top of BL and BL_bar""" 
        
        y_offset= self.pchg_ary_inst[0].uy()
        self.w_comp_inst = {}
        for i in range(self.num_subanks):
            x_offset=self.subank_width * i + self.bitcell_ary_off + self.bitcell_array.xleft_shift
            self.w_comp_inst[i]=self.add_inst(name="w_complete_{0}".format(i), 
                                              mod=self.w_complete, 
                                              offset=vector(x_offset, y_offset))
            temp = []
            if self.num_subanks==1:
                for j in range(self.w_per_row):
                    temp.extend(["bl[{0}]".format(j*self.w_size),"br[{0}]".format(j*self.w_size)])
            if self.num_subanks>1:
                for j in range(self.w_per_row):
                    temp.append("bl[{0}][{1}]".format(i,j*self.w_size))
                    temp.append("br[{0}][{1}]".format(i,j*self.w_size))

            if self.mask:
                if not self.two_level_bank:
                    temp.extend(["wreq", "bm[{0}][0]".format(i), "write_complete[{0}]".format(i), "vdd", "gnd"])
                else:
                    temp.extend(["wreq_split", "bm_split[{0}][0]".format(i),"write_complete[{0}]".format(i), "vdd", "gnd"])
            else:
                if not self.two_level_bank:
                    temp.extend(["wreq", "vdd", "write_complete[{0}]".format(i), "vdd", "gnd"])
                else:
                    temp.extend(["wreq_split", "vdd","write_complete[{0}]".format(i), "vdd", "gnd"])

            self.connect_inst(temp)

    def route_bm_write_comp(self):        
        """ Route write mask bit from write driver to write complete if self.mask """ 
        
        yoff= self.min_point_y+(self.w_per_row+self.num_ctrl_lines+self.num_subanks+4)*self.m_pitch("m1")
        for i in range(self.num_subanks):
            xoff1 = i*self.subank_width +3*self.m_pitch("m2") + contact.m1m2.height
            if self.w_per_row>1:
                xoff1 = xoff1 + self.w_per_row*self.m_pitch("m2")
            pos1 = self.w_comp_inst[i].get_pin("bm").lc()
            pos2 = vector(xoff1, pos1.y)
            pos3 = vector(xoff1, yoff)
            pos4 = vector(self.w_drv_ary_inst[i].lx()-self.m_pitch("m2"), yoff)
            if (self.two_level_bank and self.num_subanks>1):
                pos4 = pos4 - vector(self.m_pitch("m2"), 0)
            if (self.two_level_bank and self.num_subanks==1):
                pos4 = pos4 - vector(6*self.m_pitch("m2"), 0)

            pos6 = vector(self.w_drv_ary_inst[i].get_pin("bm[0]").uc().x, self.w_drv_ary_inst[0].by()+self.m1_width)
            pos5 = vector(pos4.x, pos6.y)
            self.add_wire(self.m1_stack, [pos1, pos2, pos3, pos4, pos5, pos6])


    def add_din_split_array(self):        
        """ Add DATA_IN split array if two_level_bank """ 

        self.y_offset=self.y_offset
        self.d_split_ary_inst={}
        for i in range(self.num_subanks):
            x_offset=self.subank_width * i + self.bitcell_ary_off + self.bitcell_array.xleft_shift
            offset=vector(x_offset,self.y_offset+self.d_split_array.height)
            self.d_split_ary_inst[i]=self.add_inst(name="din_split_ary_{0}".format(i),
                                                   mod=self.d_split_array,
                                                   offset=offset.scale(1,-1))
            temp = []
            for j in range(self.w_size):
                temp.extend(["din[{0}][{1}]".format(i,j),"din_split[{0}][{1}]".format(i,j)])
            if self.mask: 
                for j in range(self.w_size):
                    temp.extend(["bm[{0}][{1}]".format(i,j),"bm_split[{0}][{1}]".format(i,j)])

            if self.num_subanks>1:
                temp.extend(["rw_en1_S[{0}]".format(i),"rw_en2_S[{0}]".format(i),"reset", "go_sx[{0}]".format(i),"vdd","gnd"])
            else:
                temp.extend(["rw_en1_S", "rw_en2_S", "reset", "S", "vdd", "gnd"])
            self.connect_inst(temp)

    def add_dout_merge_array(self):        
        """ Add DATA_OUT merge array if two_level_bank """ 

        self.y_offset= self.y_offset + self.d_split_array.height
        self.d_merge_ary_inst={}
        for i in range(self.num_subanks):
            x_offset=self.subank_width * i + self.bitcell_ary_off + self.bitcell_array.xleft_shift
            offset= vector(x_offset,self.y_offset+self.d_merge_array.height)
            self.d_merge_ary_inst[i]=self.add_inst(name="dout_merge_ary_{0}".format(i),
                                                   mod=self.d_merge_array,
                                                   offset=offset.scale(1,-1))
            temp = []
            for j in range(self.w_size):
                temp.extend(["dout_merge[{0}][{1}]".format(i,j),"dout[{0}][{1}]".format(i,j)])
            if self.num_subanks>1:
                temp.extend(["Mrack[{0}]".format(i), "rreq_merge[{0}]".format(i), "reset", "go_mx[{0}]".format(i), "vdd", "gnd"])
            else:
                temp.extend(["rack_merge", "Mdout", "reset", "S", "vdd", "gnd"])
            self.connect_inst(temp)

    def add_row_dec(self):
        """ Add the hierrreqical row decoder and row_drv """ 

        self.row_dec_drv_offset=vector(self.row_dec_drv.width + self.comp_bus_width, 0)
        self.row_dec_drv_inst=self.add_inst(name="row_dec_drv", 
                                            mod=self.row_dec_drv, 
                                            offset=self.row_dec_drv_offset.scale(-1,0))
        temp = []
        for j in range(self.num_rows):
            temp.append("decode[{0}]".format(j))
        for k in range(self.num_rows):
            temp.append("gwl[{0}]".format(k))
        temp.extend(["decoder_enable", "vdd","gnd"])
        self.connect_inst(temp)
        
        shift = self.row_dec_drv.width -(self.row_dec.predecoder_width-self.row_dec.row_decoder_width)
        if shift >0:
            offset=vector(self.row_dec.width+ self.comp_bus_width + shift, 0)
        else:
            offset=vector(self.row_dec.width+ self.comp_bus_width, 0) 
        
        self.row_dec_inst=self.add_inst(name="row_dec", 
                                        mod=self.row_dec, 
                                        offset=offset.scale(-1,-1))
        temp = []
        for i in range(self.row_addr_size):
            temp.append(self.addr_name.format(i))
        for j in range(self.num_rows):
            temp.append("decode[{0}]".format(j))
        temp.extend(["vdd", "gnd"])
        self.connect_inst(temp)
        
        row_dec_en = self.row_dec_drv_inst.get_pin("en").uc()
        self.row_dec_drv_en = row_dec_en+ vector(0, self.row_dec_drv_inst.height)
        
        # Connecting output of row_dec to row_dec_drv (decode[i] is Anded with decoder_enable signal)
        for k in range(self.num_rows):
            row_dec_out = self.row_dec_inst.get_pin("decode[{0}]".format(k)).lc()
            row_dec_drv_in = self.row_dec_drv_inst.get_pin("in[{0}]".format(k)).lc()
            self.add_path("metal1",[row_dec_out, row_dec_drv_in])
            
            #The following routing is based on the metal layer of WL pin in cell_6t
            wl_pin_layer = self.bitcell_array.get_pin("wl[0]").layer
            if wl_pin_layer[0:6] == "metal1":
                route_layer = "metal3"
            else:
                route_layer = "metal4"
            
            row_dec_drv_out = self.row_dec_drv_inst.get_pin("out[{0}]".format(k)).lc()
            bitcell_wl = self.cell_ary_inst[0].get_pin("wl[{0}]".format(k))
            
            # Routing output of row_dec_drv directly to bitcell_array
            if self.num_subanks==1:
                if bitcell_wl.layer[0:6] == "metal1":
                    layer = "metal1" 
                else:
                    layer = "metal3"      
                self.add_path(layer, [row_dec_drv_out, bitcell_wl.lc()])

            # Routing output of row_dec_drv to each subank to gated with go[i]
            if self.num_subanks>1:
                last_drv_in = self.bitcell_ary_drv_inst[self.num_subanks-1].get_pin("in[{0}]".format(k)).lc()
                self.add_path(route_layer, [row_dec_drv_out, last_drv_in])

        # calculating the location of the subank decoder in case there is no col_mux_array
        self.vertical_gap = max(self.well_space, 2*self.m_pitch("m1")) 
        if self.mux_addr_size == 0:
            self.subank_dec_x_off = self.row_dec_inst.lx() -(self.addr_size+2)*self.m_pitch("m2")-\
                                    2*(self.pow_width+self.m_pitch("m1"))
                                 
            if self.two_level_bank:
                self.subank_dec_y_off = max(self.row_dec.predecoder_height, 
                                            -self.d_merge_ary_inst[0].by())
            else:
                self.subank_dec_y_off = self.row_dec.predecoder_height

    def add_col_mux_dec(self):
        """ Create a decoder to decode col_mux select lines if the words_per_row > 1 """
        
        if self.mux_addr_size == 1:
            self.mux_decoder = self.inv
        if self.mux_addr_size == 2:
            self.mux_decoder = self.row_dec.pre2_4
        if self.mux_addr_size > 2:
            debug.error("more than 4 way column mux is not supported!",-1)

        # Place the col_mux decoder below the the row decoder (with some space for wells)
        x_off = self.mux_decoder.width  + self.comp_bus_width
        self.vertical_gap = max(self.well_space, 2*self.m_pitch("m1")) 
        y_off = self.row_dec.predecoder_height + self.mux_decoder.height + 2*self.vertical_gap
        if self.mux_addr_size == 1:
            y_off = y_off + self.mux_decoder.height

        self.mux_dec_inst=self.add_inst(name="col_mux_decoder", 
                                        mod=self.mux_decoder, 
                                        offset=vector(x_off,y_off).scale(-1,-1))
        temp = []
        if self.mux_addr_size == 1:
            self.connect_inst([self.addr_name.format(self.row_addr_size), "pre_sel[1]", "vdd", "gnd"])
        else:
            for i in range(self.mux_addr_size):
                temp.append(self.addr_name.format(i + self.row_addr_size))
            for j in range(self.w_per_row):
                temp.append("pre_sel[{0}]".format(j))
            temp.extend(["vdd", "gnd"])
            self.connect_inst(temp)

        # Update the location of the subank decoder in case there is a col_mux_array
        if self.mux_addr_size > 0:
            self.subank_dec_x_off = min (self.row_dec_inst.lx(), self.mux_dec_inst.lx()) - \
                                         2*(self.pow_width+self.m_pitch("m1")) - \
                                         (self.addr_size+2)*self.m_pitch("m2")  

            if self.two_level_bank:
                self.subank_dec_y_off = max(self.row_dec.predecoder_height+ self.mux_decoder.height+\
                                            2*self.vertical_gap, -self.d_merge_ary_inst[0].by())
            else :
                self.subank_dec_y_off = self.row_dec.predecoder_height + self.mux_decoder.height + \
                                        2*self.vertical_gap

    def add_subank_dec(self):
        """ Create a decoder to decode subank select lines if the subank_addr_size > 0 """
        
        if self.subank_addr_size == 1:
            self.subank_dec = self.inv
        if self.subank_addr_size == 2:
            self.subank_dec = self.row_dec.pre2_4
        if self.subank_addr_size == 3:
            self.subank_dec = self.row_dec.pre3_8
        if self.subank_addr_size > 3:
            debug.error("more than 8 column per bank is not supported!",-1)

        offet = vector(self.subank_dec_x_off,self.subank_dec_y_off)
        self.subank_dec_inst=self.add_inst(name="subank_addr_decoder", 
                                           mod=self.subank_dec, 
                                           offset=offet.scale(1,-1), 
                                           mirror = "MY")
        temp = []
        if self.subank_addr_size == 1:
            self.connect_inst([self.addr_name.format(self.row_addr_size + self.mux_addr_size),"cs[1]", "vdd", "gnd"])
        else:
            for i in range(self.subank_addr_size):
                temp.append(self.addr_name.format(i+self.row_addr_size+self.mux_addr_size))
            for j in range(self.num_subanks):
                temp.append("cs[{0}]".format(j))
            temp.extend(["vdd", "gnd"])
            self.connect_inst(temp)

        if self.subank_addr_size == 1:
            col_dec_drv_x = self.subank_dec_inst.lx()-self.m_pitch("m1")
        else:
            col_dec_drv_x = self.subank_dec_inst.lx()

        # Add drv to gate subank select signals with PCHG signal from ctrl logic and create go[i] signals
        offset=vector(col_dec_drv_x, self.subank_dec_y_off)
        self.subank_dec_drv_inst=self.add_inst(name="subank_drv", 
                                               mod=self.subank_dec_drv, 
                                               offset=offset.scale(1,-1), 
                                               mirror = "MY")
        temp = []
        if self.subank_addr_size == 1:
            temp.extend([self.addr_name.format(self.row_addr_size + self.mux_addr_size),"cs[1]"])
        if self.subank_addr_size > 1:
            for i in range(self.num_subanks):
                temp.append("cs[{0}]".format(i))
        for i in range(self.num_subanks):
            temp.append("go[{0}]".format(i))
        temp.extend(["pchg", "vdd", "gnd"])
        self.connect_inst(temp)
        self.subank_dec_drv_height=self.subank_dec_drv.height

        if self.two_level_bank:
            self.subank_dec_drv_inst2=self.add_inst(name="subank_drv2", 
                                                    mod=self.subank_dec_drv2, 
                                                    offset=self.subank_dec_drv_inst.ll(), 
                                                    mirror = "MY")
            temp = []
            for i in range(self.num_subanks):
                 temp.append("go[{0}]".format(i))
            for i in range(self.num_subanks):
                 temp.append("go_s[{0}]".format(i))
            temp.extend(["S", "vdd", "gnd"])
            self.connect_inst(temp)

            # connect the output of subank_dec_drv to input of subank_dec_d2rv
            for i in range(self.num_subanks):
                pos1=self.subank_dec_drv_inst2.get_pin("in[{0}]".format(i)).lc()
                pos4=self.subank_dec_drv_inst.get_pin("out[{0}]".format(i)).lc()
                pos2=vector(pos4.x-0.5*self.m1_width, pos1.y)
                pos3=vector(pos2.x, pos4.y)
                self.add_path("metal1", [pos1, pos2, pos3, pos4])

        
        # connect the output of subank_dec to input of subank_dec_drv
        for i in range(self.num_subanks):
            subank_drv_in = self.subank_dec_drv_inst.get_pin("in[{0}]".format(i))
            # subank decoder is an inverter
            if (self.subank_addr_size == 1):
                subank_drv_vdd = self.subank_dec_drv_inst.get_pin("vdd").lc()
                subank_drv_gnd = self.subank_dec_drv_inst.get_pins("gnd")[0].lc()
                subank_dec_vdd = self.subank_dec_inst.get_pin("vdd").lc()
                subank_dec_gnd = self.subank_dec_inst.get_pin("gnd").lc()
                self.add_path("metal1", [subank_drv_vdd, subank_dec_vdd ])
                self.add_path("metal1", [subank_drv_gnd, subank_dec_gnd ])
                
                if (i%2):
                    subank_dec_out = self.subank_dec_inst.get_pin("Z") 
                    self.add_wire(self.m1_stack, [(subank_dec_out.rx()+0.5*self.m2_width, 
                                                   subank_dec_out.by()), subank_drv_in.lc()])

                else:
                    pin = self.subank_dec_inst.get_pin("A")
                    subank_dec_out = vector(pin.rx()+0.5*contact.m1m2.width, pin.uy())  
                    self.add_via(self.m1_stack, pin.lr()- vector(0, self.via_shift("v1")))
                    
                    xoff=self.subank_dec_inst.lx()-self.m_pitch("m1")
                    self.add_path("metal1", [(xoff+0.5*self.m2_width, subank_drv_in.lc().y),
                                             (subank_drv_in.uc().x, subank_drv_in.lc().y)])
                    
                    self.add_via(self.m1_stack, (xoff- 0.5*self.m2_width, subank_drv_in.lc().y))
                    pos1=vector(subank_dec_out.x, subank_dec_out.y)
                    pos2=vector(pos1.x, subank_dec_out.y-self.m_pitch("m1"))
                    pos3=vector(self.subank_dec_inst.lx()-self.m_pitch("m1"),pos2.y)
                    pos4=vector(pos3.x,subank_drv_in.lc().y)
                    self.add_path("metal2", [pos1, pos2, pos3, pos4], width=contact.m1m2.width)
                    
            # subank decoder is a 2:4 or 3:8 decoder
            if (self.subank_addr_size > 1):
                subank_dec_out = self.subank_dec_inst.get_pin("out[{0}]".format(i)).uc()
                mid_pos=(subank_dec_out.x, subank_drv_in.lc().y)
                self.add_path("metal1",[subank_dec_out, mid_pos, subank_drv_in.lc()])
        
        if (self.subank_addr_size > 1):
            for i in range(len(self.subank_dec_drv_inst.get_pins("vdd"))):
                subank_drv_vdd = self.subank_dec_drv_inst.get_pins("vdd")[i].lc()
                subank_dec_vdd = self.subank_dec_inst.get_pins("vdd")[i].lc()
                self.add_path("metal1", [subank_drv_vdd, subank_dec_vdd])
            for i in range(len(self.subank_dec_drv_inst.get_pins("gnd"))):
                subank_drv_gnd = self.subank_dec_drv_inst.get_pins("gnd")[i].lc()
                subank_dec_gnd = self.subank_dec_inst.get_pins("gnd")[i].lc()
                self.add_path("metal1", [subank_drv_gnd, subank_dec_gnd])

    def add_addr_split_ary(self):
        """ Add address splits on the left side of row-decoder, above col_dec (if num_bank > 1)""" 
   
        y_offset=self.subank_dec_y_off-self.subank_dec_drv_height-(self.m_pitch("m1")+self.well_space)
        x_offset=self.subank_dec_x_off-self.addr_split_array.width
        self.addrs_ary_inst=self.add_inst(name="addr_split_ary", 
                                          mod=self.addr_split_array,
                                          offset=vector(x_offset,y_offset).scale(1,-1))
        temp = []
        for i in range(self.addr_size):
            temp.extend(["addr[{0}]".format(i), "addr_split[{0}]".format(i)])
        temp.extend(["rw_en1_S", "rw_en2_S", "reset", "S", "vdd", "gnd"])
        self.connect_inst(temp)

    def add_ctrl_merge_cells(self):
        """ Add ctrl merge array on the top of ctrl split array
            ack, rack and wack signals are mergeed if there are more than one bank """ 

        y_offset=self.addrs_ary_inst.uy() + max(9*self.m_pitch("m2"), 
                 (self.addr_size+1)*self.m_pitch("m1"))
        x_offset=self.subank_dec_x_off - 3*self.ctrl_merge_cell.width - \
                 7*self.m_pitch("m1")-self.bitcell.width
        self.ack_merge_cell_inst=self.add_inst(name="ack_merge_cell", 
                                               mod=self.ctrl_merge_cell,
                                               offset=vector(x_offset,y_offset))
        temp = ["ack_merge", "ack", "Mack", "pchg", "reset", "S", "vdd", "gnd"]
        self.connect_inst(temp)
        
        x_offset=self.ack_merge_cell_inst.rx() + 3*self.m_pitch("m1")
        self.rack_merge_cell_inst=self.add_inst(name="rack_merge_cell", 
                                                mod=self.ctrl_merge_cell,
                                                offset=vector(x_offset,y_offset))
        temp = ["rack_merge", "rack", "Mrack", "rreq_merge", "reset", "S", "vdd", "gnd"]
        self.connect_inst(temp)

        x_offset=self.rack_merge_cell_inst.rx() + 3*self.m_pitch("m1")
        self.wack_merge_cell_inst=self.add_inst(name="wack_merge_cell", 
                                                mod=self.ctrl_merge_cell,
                                                offset=vector(x_offset,y_offset))
        temp = ["wack_merge", "wack", "Mwack", "wreq_split", "reset", "S", "vdd", "gnd"]
        self.connect_inst(temp)

    def add_ctrl_split_ary(self):
        """ Add ctrl split array on the top of address split array
            w, r, rw, rreq and wreq signals are splitted if there are more than one bank""" 

        y_offset= self.ack_merge_cell_inst.by()
        x_offset= self.ack_merge_cell_inst.lx()-3*self.m_pitch("m1") - self.ctrl_split_array.width
        self.ctrls_ary_inst=self.add_inst(name="ctrl_split_ary", 
                                          mod=self.ctrl_split_array,
                                          offset=vector(x_offset,y_offset))
        self.connect_inst(["rw", "rw_split", "w", "w_split", "r", "r_split", "rreq", "rreq_split", 
                           "wreq", "wreq_split", "rw_en1_S", "rw_en2_S", "reset", "S", "vdd", "gnd"])
    
    def add_ctrl_logic(self):
        """ Add ctrl_logic on the left side of row-decoder, above col_dec (if any)""" 
        
        x_offset= self.row_dec_inst.lx()-2*self.pow_width-3*self.m_pitch("m1")- self.ctrl_logic.height

        above_row_dec = self.row_dec_inst.get_pin("A[{0}]".format(self.row_addr_size-1)).by()+\
                        self.m_pitch("m2")*(self.row_addr_size+1)

        if not self.two_level_bank: 
            if self.num_subanks == 1:
                y_offset = above_row_dec
            else:
                above_subank_dec = self.subank_dec_drv_inst.uy()+\
                                  self.m_pitch("m1")*(self.num_subanks+self.addr_size+2)
                y_offset = max(above_row_dec, above_subank_dec)

        else:
            #(9+self.num_subanks): 3*(en1_M, en2_M) + vdd + gnd + space * go[i]
            y_offset=max(self.ack_merge_cell_inst.uy() + (9+self.num_subanks)*self.m_pitch("m1"), 
                         above_row_dec+ 2*self.m_pitch("m2")+ (self.num_subanks+1)*self.m_pitch("m1"))
        
        self.ctrl_logic_inst=self.add_inst(name="ctrl_logic", 
                                           mod=self.ctrl_logic, 
                                           offset=vector(x_offset, y_offset).scale(1,1),
                                           mirror="MX",
                                           rotate=90)
        temp = []
        if self.two_level_bank:
            temp.extend(["reset", "r_split", "w_split", "rw_split", "ack_merge", "rack_merge",
                         "rreq_split", "rreq_merge", "wreq_split", "wack_merge"])
        else:
            temp.extend(["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"])
        for i in range(self.num_subanks):
            temp.append("write_complete[{0}]".format(i))
        for i in range(self.num_subanks):
            temp.append("data_ready[{0}]".format(i))
        if self.num_subanks>1:
            for i in range(self.num_subanks):
                temp.append(self.go_name.format(i))
        temp.extend(["sen","wen", "pchg", "decoder_enable"])
        if self.power_gate:
            temp.extend(["sleep"])
        temp.extend(["vdd", "gnd"])
        self.connect_inst(temp)

    def add_power_lines(self):
        """ Add two pairs of vdd/gnd rail for each subank so vdd/gnd of all sub-modules be connected""" 
       
        # The min point for data_out is the bottom of merge_arary if two_level_bank or
        # bottom of write-drv if not two_level_bank or bottom of go driver if num_subanks>1
        if self.two_level_bank:
            dout_min_point = self.d_merge_ary_inst[0].by()
        else:
            if self.num_subanks >1: 
                dout_min_point = min(self.go_drv_inst[0].by(), self.w_drv_ary_inst[0].by()) 
            else: 
                dout_min_point = self.w_drv_ary_inst[0].by()
        
        # The min Y-point is either the bottom of the decoders or the min data point
        if (self.mux_addr_size > 0):
            min_y_dec_side = min (self.mux_dec_inst.by(), dout_min_point- 2*self.m_pitch("m1")) 
            self.min_x_row_dec = min (self.row_dec_inst.lx(), self.mux_dec_inst.lx())
        
        else:
            min_y_dec_side = min(self.row_dec_inst.by()-self.row_dec.predecoder_height, dout_min_point- 2*self.m_pitch("m1")) 
            self.min_x_row_dec = self.row_dec_inst.lx() - self.m1_width
            
        if self.num_subanks > 1:
            min_y_dec_side = min_y_dec_side- self.num_ctrl_lines*self.m_pitch("m2")- self.w_per_row*self.m_pitch("m1")
        
        # This is for address bus position
        self.addr_x_offset=self.min_x_row_dec - (2*self.pow_width+2*self.m_pitch("m1"))
        
        # The minimum X-point is the left of the ctrl_logic or col_dec_drv.
        self.min_point_x = self.addr_x_offset - self.ctrl_logic.height - 2*self.m_pitch("m1")
        
        # If num_subnak > 1 min_y offset is for (go[i] + vdd + gnd +pchg) routing to subank_decoder
        if self.num_subanks > 1:
            self.min_point_y = min_y_dec_side-(self.num_subanks+3)*self.m_pitch("m1")
            self.min_point_x = min(self.min_point_x, self.subank_dec_drv_inst.lx() -\
                                   self.m_pitch("m1")*(self.num_subanks+3))
        else:
            self.min_point_y = min_y_dec_side -2*self.m_pitch("m1")

        # If two_level banking min_x offset can be for split-merge ctrl cells
        if self.two_level_bank:
            self.min_point_x = min(self.min_point_x,self.addrs_ary_inst.lx()-self.m_pitch("m1"), 
                                   self.ctrls_ary_inst.lx()-self.m_pitch("m1"))
            if self.num_subanks > 1:
                self.min_point_x = min(self.min_point_x, self.subank_dec_drv_inst2.lx() - \
                                       self.m_pitch("m1")*(self.num_subanks+3))

        # The max Y-point is the w_complete_inst top plus w_complete routing OR the ctrl logic top
        # OR row_dec_drv top + internal ctrl signal routing to ctrl_logic
        w_complete_max_y = (self.w_comp_inst[0].uy() + (self.num_subanks+1)*self.m_pitch("m1"))
        ctrl_logic_max_y = self.ctrl_logic_inst.uy()+(2*self.num_subanks+7)*self.m_pitch("m2")
        row_dec_max_y = (self.row_dec_drv_inst.uy()+(2*self.num_subanks+7)*self.m_pitch("m2"))
        
        self.max_point_y = max (w_complete_max_y, ctrl_logic_max_y, row_dec_max_y)
        
        # Calculating the height of vertical address bus
        last_addr_off1=self.row_dec_inst.get_pin("A[{0}]".format(self.row_addr_size-1)).by()+\
                       self.m_pitch("m2")*self.row_addr_size
        
        if self.two_level_bank:
            last_addr_off2= self.ctrls_ary_inst.by() 
            self.addr_height= max(last_addr_off1, last_addr_off2)-self.min_point_y

        else:
            self.addr_height= last_addr_off1- self.min_point_y
            if self.num_subanks >1:
                self.addr_height = max (self.addr_height, self.subank_dec_drv_inst.uy() +\
                                        self.m_pitch("m1")*self.addr_size - self.min_point_y)
        
        # Defining the height of bank including all the modules and routings
        # Power_heght is the height of vertical vdd and gnd rails
        self.power_height=self.max_point_y - self.min_point_y
        self.height = self.power_height
        
        # Add two m2_pitch for vdd and gnd connection of ctrl_logic if condition is true
        if self.max_point_y >= self.ctrl_logic_inst.uy():
            self.height = self.power_height + 4*self.m_pitch("m2")

        # If two_level_bank, 6 metal rails are added to connect data split to addr/ctrl split ctrl
        if self.two_level_bank:
            self.height= self.power_height + 9* self.m_pitch("m2")
        
        # Add vdd and gnd rails as power pins for each sub-bank
        self.vdd_x_offset={}
        self.gnd_x_offset={}
        self.vdd2_x_offset={}
        self.gnd2_x_offset={}

        vdd_rail_height = self.pchg_ary_inst[0].uy() - self.min_point_y+self.m1_width
        vdd2_rail_height = self.w_comp_inst[0].uy() - self.min_point_y+self.m1_width
        
        for i in range(self.num_subanks):
            self.gnd_x_offset[i]=i*self.subank_width + 5*self.m_pitch("m2")
            if self.w_per_row>1:
                self.gnd_x_offset[i]=i*self.subank_width + (5+self.w_per_row)*self.m_pitch("m2")
            self.vdd_x_offset[i]=self.gnd_x_offset[i] + self.pow_pitch
            
            self.gnd2_x_offset[i]=self.cell_ary_inst[i].rx() + self.m_pitch("m2")
            self.vdd2_x_offset[i]=self.gnd2_x_offset[i] + self.pow_pitch

            a = [self.vdd_x_offset[i], self.vdd2_x_offset[i]]
            b = [ vdd_rail_height, vdd2_rail_height]
            for (off, height) in zip (a,b):
                self.add_rect(layer="metal2", 
                              offset=(off, self.min_point_y), 
                              width=self.pow_width, 
                              height=height)
                self.add_layout_pin(text="vdd", 
                                    layer="metal2", 
                                    offset=(off, self.min_point_y), 
                                    width=self.pow_width, 
                                    height=self.pow_width)
            
            a = [self.gnd_x_offset[i], self.gnd2_x_offset[i]]
            for (off, height) in zip (a,b):
                self.add_rect(layer="metal2", 
                              offset=(off, self.min_point_y), 
                              width=self.pow_width, 
                              height=height)
                self.add_layout_pin(text="gnd", 
                                    layer="metal2", 
                                    offset=(off, self.min_point_y), 
                                    width=self.pow_width, 
                                    height=self.pow_width)

        # calculating the width of bank including all the modules and routings
        self.width=self.cell_ary_inst[self.num_subanks-1].rx()+2*self.pow_pitch+\
                   (self.num_subanks+1)*self.m_pitch("m1")- self.min_point_x

        # If two_level_bank, 8 metal rails added for data split/merge to addr/ctrl split/merge ctrl
        if self.two_level_bank:
            self.width= self.width + 8*self.m_pitch("m1")
        
    def add_and_route_address_bus(self):
        """ Add address pins for row decoder, col decoder and col_mux decoder input address"""

        for i in range(self.addr_size):
            off=vector(self.addr_x_offset-(i+1)*(self.m_pitch("m2")),self.min_point_y)
            self.add_rect(layer="metal2", 
                          offset=off, 
                          width=contact.m1m2.width, 
                          height=self.addr_height)

        # Connecting input address lines of row decoder to address pins
        for i in range(self.row_addr_size):
            addr_off= self.row_dec_inst.get_pin("A[{0}]".format(i)).ll() 
            addr_width=self.addr_x_offset-(i+1)*(self.m_pitch("m2")) - addr_off.x
            y_off = addr_off.y+i*self.m_pitch("m2")
            self.add_rect(layer="metal3", 
                          offset=vector(addr_off.x, y_off), 
                          width=addr_width, 
                          height=self.m3_width)
            self.add_via(self.m2_stack,(addr_off.x, y_off))
            self.add_via(self.m2_stack,(addr_off.x+addr_width+contact.m2m3.height-self.via_shift("v1"), y_off), 
                         rotate=90)
        
        # Connecting input address lines of mux decoder (inverter or 2:4 decoder) to address pins
        for i in range(self.mux_addr_size):
            if self.mux_addr_size == 1:
                addr_off = self.mux_dec_inst.get_pin("A").ll()
                self.add_via(self.m2_stack,(addr_off.x-drc["metal3_enclosure_via2"]-\
                                            self.m1_width,addr_off.y-self.via_shift("v1")))

            if self.mux_addr_size > 1:
                addr_off = self.mux_dec_inst.get_pin("in[{0}]".format(i)).ll()
                self.add_via(self.m2_stack, (addr_off.x+contact.m1m2.width, addr_off.y+i*self.m_pitch("m2")), rotate=90)
            
            addr_width=self.addr_x_offset-addr_off.x-(i+1+self.row_addr_size)*(self.m_pitch("m2")) 
            yoff = addr_off.y+i*self.m_pitch("m2")
            self.add_rect(layer="metal3", 
                           offset=vector(addr_off.x, yoff), 
                           width=addr_width, 
                           height=self.m3_width)
            self.add_via(self.m2_stack, (addr_off.x+addr_width, yoff-self.via_shift("v1")))
        
        # Connecting input address lines of subank decoder (inverter or 2:4 decoder) to address pins
        for i in range(self.subank_addr_size):
            if self.subank_addr_size == 1:
                addr_off = self.subank_dec_inst.get_pin("A").lr() 
            if self.subank_addr_size > 1:
                addr_off = self.subank_dec_inst.get_pin("in[{0}]".format(i)).ll()
            
            addr_width=self.addr_x_offset- addr_off.x - (i+1+self.row_addr_size+self.mux_addr_size)*(self.m_pitch("m2")) 
            yoff = addr_off.y+i*self.m_pitch("m2")
            self.add_rect(layer="metal3", 
                          offset=vector(addr_off.x, yoff), 
                          width=addr_width, 
                          height=self.m3_width)
            self.add_via(self.m2_stack, (addr_off.x , yoff-self.via_shift("v2")))
            self.add_via(self.m2_stack, (addr_off.x + addr_width+contact.m2m3.height-self.via_shift("v1"), yoff), rotate=90)
        
        # Connecting output of address split to address bus if two_level_bank
        if self.two_level_bank:
            for i in range(self.addr_size):
                addr_out_off= self.addrs_ary_inst.get_pin("Q[{0}]".format(self.addr_size-1-i)).uc()
                addr_end_x = self.addr_x_offset-(self.addr_size-i)*self.m_pitch("m2") 
                addr_end_y = addr_out_off.y+(i+1)*self.m_pitch("m1")
                self.add_wire(self.m1_stack, [addr_out_off,(addr_out_off.x, addr_end_y),(addr_end_x,addr_end_y)])
                self.add_via(self.m1_stack, (addr_end_x, addr_end_y-0.5*self.m1_width-self.via_shift("v1")))

            # Creating input address pins for address split array if two_level_bank
            for i in range(self.addr_size):
                addr_in_off= self.addrs_ary_inst.get_pin("D[{0}]".format(i))
                addr_pin_x= self.min_point_x-(self.num_subanks+ 2*self.num_split_ctrl_lines)*self.m_pitch("m1")
                addr_pin_y= addr_in_off.by()-(i+1)*self.m_pitch("m2")
                self.add_path("metal3", [addr_in_off.uc(), (addr_in_off.uc().x,addr_pin_y), (addr_pin_x,addr_pin_y)])
                self.add_layout_pin(text="addr[{0}]".format(i),
                                    layer="metal3",
                                    offset=(addr_pin_x,addr_pin_y-0.5*self.m3_width), 
                                    width=self.m3_width, 
                                    height=self.m3_width)
        else:
            # Creating input address pins if not two_level_bank
            for i in range(self.addr_size):
                y_off = self.row_dec_inst.get_pin("A[{0}]".format(self.row_addr_size-1)).by() +\
                        (self.row_addr_size-1) * self.m_pitch("m2")
                if self.num_subanks >1:
                    y_off =self.subank_dec_drv_inst.uy() + self.addr_size * self.m_pitch("m1")

                x_off=self.min_point_x-self.num_subanks*self.m_pitch("m1")
                self.add_via(self.m1_stack, (self.addr_x_offset-(i+1)*(self.m_pitch("m2")), 
                             y_off-i*self.m_pitch("m1")-self.via_shift("v1")))
                self.add_rect(layer="metal1",
                              offset=(x_off,y_off-i*self.m_pitch("m1")), 
                              width=self.addr_x_offset-(i+1)*(self.m_pitch("m2")) - x_off, 
                              height=self.m1_width)
                self.add_layout_pin(text="addr[{0}]".format(i),
                                    layer="metal1",
                                    offset=(x_off,y_off-i*self.m_pitch("m1")), 
                                    width=self.m1_width, 
                                    height=self.m1_width)

    def add_ctrl_bus(self):
        """ Create the ctrl central bus for sen, wen and pchg (spli/merge ctrl if two_level_bank)"""

        self.ctrl_line_xoffset={}
        height = self.w_comp_inst[0].by() - self.min_point_y
        if self.num_subanks==1:
            drv = [self.pchg_ary_inst, self.s_amp_ary_inst, self.w_drv_ary_inst]
            pin_name="en"
        if self.num_subanks>1:
            drv = [self.pchg_drv_inst]
            pin_name="in[0]"

        for i in range(self.num_subanks):
            for j in range(3):
                x_offset=i*self.subank_width+ j*self.m_pitch("m2")+self.m2_width
                y_offset = self.min_point_y+(j+2)*self.m_pitch("m1")
                if self.w_per_row>1:
                    x_offset=i*self.subank_width+(j+self.w_per_row)*self.m_pitch("m2")
                if i ==0:
                    self.add_rect(layer="metal2", 
                                  offset=vector(x_offset, self.min_point_y), 
                                  width=self.m2_width, 
                                  height= height)
                    self.ctrl_line_xoffset[j] = x_offset
                    if self.num_subanks != 1:
                        self.add_via(self.m1_stack,(x_offset,y_offset))
                else:
                    self.add_rect(layer="metal2", 
                                  offset=vector(x_offset, self.min_point_y), 
                                  width=self.m2_width, 
                                  height= height)
                    self.add_rect(layer="metal1", 
                                   offset=vector(x_offset - self.subank_width, y_offset), 
                                   width=self.subank_width, 
                                   height= self.m1_width)
                    self.add_via(self.m1_stack, (x_offset, y_offset-self.via_shift("v1")))
            
                if self.num_subanks==1:
                    self.add_rect(layer="metal1", 
                                  offset=(x_offset, drv[j][i].get_pin(pin_name).by()), 
                                  width=drv[j][i].get_pin(pin_name).lx()-x_offset+i*self.subank_width, 
                                  height= self.m1_width)
                    self.add_via(self.m1_stack, (x_offset, drv[j][i].get_pin(pin_name).by()-\
                                                 contact.m1m2.height+self.via_shift("v1")))

                else:
                    xoff=i*self.subank_width+self.m2_width
                    pin = self.pchg_drv_inst[i].get_pin("in[0]").ll()
                    if self.w_per_row>1:
                        xoff=i*self.subank_width+self.w_per_row*self.m_pitch("m2")
                    self.add_rect(layer="metal1", 
                                  offset=(xoff, pin.y), 
                                  width=pin.x-xoff, 
                                  height= self.m1_width)
                    self.add_via(self.m1_stack, (xoff, pin.y- contact.m1m2.height+self.via_shift("v1")))

            #connect data_ready to sen and write driver to pchg
            pin_list = [self.data_ready_inst[i].get_pin("sen").ll(), 
                        self.w_drv_ary_inst[i].get_pin("pchg").ll()]
            for k in range(2):
                pin = pin_list[k]
                x_offset=i*self.subank_width+ (1-k)*self.m_pitch("m2")+self.m2_width
                if self.w_per_row>1:
                    x_offset = x_offset+self.w_per_row*self.m_pitch("m2")-self.m2_width
                
                self.add_rect(layer="metal1", 
                              offset=(x_offset, pin.y), 
                              width=pin.x-x_offset, 
                              height= self.m1_width)
                self.add_via(self.m1_stack, (x_offset, pin.y- contact.m1m2.height+self.via_shift("v1")))

    def add_data_ready_bus(self):
        """ Create the data_ready ctrl bus lines next to middle gnd rail """
        
        self.data_ready_xoffset={}
        for j in range(self.data_ready_size):
            self.data_ready_xoffset[j] = -(j+1)*self.m_pitch("m2")
            self.add_rect(layer="metal2", 
                          offset=vector(self.data_ready_xoffset[j], self.min_point_y), 
                          width=contact.m2m3.first_layer_height, 
                          height= self.power_height)
        
        # Connect the output of data ready nand gate to data ready bus
        for i in range(self.num_subanks):
            x_offset=self.data_ready_xoffset[i]
            pin = self.data_ready_inst[i].get_pin("dr").ll()
            width=pin.x + (i+1)*self.m_pitch("m2")
            if (self.num_subanks == 1 and self.w_per_row == 1):
                self.add_rect(layer="metal1", 
                              offset=vector(x_offset, pin.y), 
                              width=width, 
                              height= self.m1_width)
                self.add_via(self.m1_stack,(x_offset, pin.y-self.via_shift("v1")))
            else:
                yoff = self.data_ready_inst[i].by()-(i+1)*self.m_pitch("m1")
                dr_pos1= (x_offset, yoff)
                dr_pos3= pin -vector(0.5*contact.m1m2.width, 0)
                dr_pos2= (dr_pos3.x, yoff)
                self.add_wire(self.m1_stack,[dr_pos1, dr_pos2, dr_pos3])
                self.add_via(self.m1_stack,(x_offset, yoff))
                self.add_via(self.m1_stack,(dr_pos3.x-0.5*self.m2_width, dr_pos3.y-self.via_shift("v1")))

    def add_w_complete_bus(self):
        """ Create the w_complete ctrl bus lines next to data_ready ctrl bus """

        self.w_complete_xoffset={}
        for j in range(self.write_comp_size):
            self.w_complete_xoffset[j]= -(self.data_ready_size + j + 1) *self.m_pitch("m2")
            self.add_rect(layer="metal2", 
                          offset=vector(self.w_complete_xoffset[j], self.min_point_y), 
                          width=contact.m2m3.first_layer_height, 
                          height= self.power_height)

        # Connect the output of w_complete to write complete bus
        for i in range(self.num_subanks):
            x_offset=self.w_complete_xoffset[i]
            y_offset= self.w_comp_inst[i].uy() + (i+1)*self.m_pitch("m1")
            wc_pos1= (x_offset,y_offset)
            wc_pos3= self.w_comp_inst[i].get_pin("write_complete").uc()
            wc_pos2= (wc_pos3.x,y_offset) 
            self.add_wire(self.m1_stack,[wc_pos1, wc_pos2, wc_pos3])
            self.add_via(self.m1_stack,(self.w_complete_xoffset[i], y_offset-0.5*self.m1_width))
            self.row_dec_drv_inst

    def add_col_mux_sel_routing(self):
        """ route the col_mux decoder outputs to sel signals of col_mux_array"""
        
        if self.mux_addr_size==1:
            #There is an inverter
            
            mux_out = self.mux_dec_inst.get_pin("Z")
            self.add_rect(layer="metal1", 
                          offset= mux_out.ll(), 
                          width = -mux_out.lx(), 
                          height=self.m1_width)
            self.add_via(self.m1_stack, (0, mux_out.by()-self.via_shift("v1")))
            
            mux_in = self.mux_dec_inst.get_pin("A").ll()
            width = self.m_pitch("m1") - mux_in.x
            self.add_rect(layer="metal3", 
                          offset=mux_in, 
                          width=width, 
                          height=self.m3_width)
            self.add_via(self.m2_stack, (mux_in.x+width-0.5*self.m1m2_m2m3_fix, mux_in.y))
            self.add_via(self.m1_stack, (mux_in.x-contact.m1m2.width, mux_in.y-self.via_shift("v1")))
            self.add_rect(layer="metal2", 
                          offset=(mux_in.x-2*self.m2_width, mux_in.y-self.via_shift("v1")-self.m2_width), 
                          width=3*self.m2_width, 
                          height=util_ceil(self.m2_minarea/self.m2_width))

        if self.mux_addr_size>1:
            # There is a 2:4 decoder
            for j in range(self.w_per_row):
                mux_dec_out = self.mux_dec_inst.get_pin("out[{0}]".format(j)).ll()
                self.add_via(self.m2_stack, ((j)*self.m_pitch("m1")-0.5*self.m1m2_m2m3_fix, mux_dec_out.y))

                width_left = j*self.m_pitch("m1") - mux_dec_out.x
                self.add_rect(layer="metal3", 
                              offset=mux_dec_out, 
                              width=width_left, 
                              height=self.m3_width)
                self.add_via(self.m2_stack, (mux_dec_out.x-contact.m1m2.width, mux_dec_out.y))

        # sel connection for col_mux within each columns
        for i in range(self.num_subanks):
            if self.mux_addr_size > 0:
                for j in range(self.w_per_row):
                    x_offset2 = j*self.m_pitch("m1") + i*self.subank_width
                    self.add_rect(layer="metal2",
                                  offset=vector(x_offset2, self.min_point_y), 
                                  width=self.m2_width, 
                                  height=-self.min_point_y)
                    if self.num_subanks==1:
                        pos = self.mux_ary_inst[i].get_pin("sel[{0}]".format(j)).ll()
                        width_right = pos.x + j*self.m_pitch("m1")
                    if self.num_subanks>1:
                        pos = self.go_drv_inst[i].get_pin("in[{0}]".format(j)).ll()
                        width_right = self.go_drv_inst[0].get_pin("in[{0}]".format(j)).lx() - j*self.m_pitch("m1")
                    
                    self.add_via(self.m1_stack,(x_offset2, pos.y))
                    self.add_rect(layer="metal1", 
                                  offset=(x_offset2, pos.y), 
                                  width=width_right, 
                                  height=self.m1_width)

        # sel connection for sel bus between columns
        for j in range(self.w_per_row):
            if self.mux_addr_size > 0:
                for i in range(self.num_subanks-1):
                    x_off2 = j*self.m_pitch("m1") + i*self.subank_width
                    y_off2 = self.min_point_y+(j+self.num_ctrl_lines+self.num_subanks+3)*self.m_pitch("m1")
                    self.add_rect(layer="metal1", 
                                  offset=(x_off2, y_off2), 
                                  width=self.subank_width, 
                                  height=self.m1_width)
                    self.add_via(self.m1_stack, (x_off2, y_off2-self.via_shift("v1")))
                if self.num_subanks > 1:
                    x_off2 = (j) *self.m_pitch("m1") + (self.num_subanks-1)* self.subank_width
                    self.add_via(self.m1_stack, (x_off2, y_off2-self.via_shift("v1")))
                    

    def go_signal_routing(self):
        """ route GO signals from column decoder drv to drivers in each column """

        if self.two_level_bank:
            mod = self.subank_dec_drv_inst2
        else:
            mod = self.subank_dec_drv_inst
        
        self.x_offset_go={}
        for i in range(self.num_subanks):
            self.x_offset_go[i] = self.bitcell_ary_drv_inst[i].get_pin("en").lx()
            self.add_rect(layer="metal2", 
                          offset=(self.x_offset_go[i], self.min_point_y), 
                          width=self.m2_width, 
                          height=self.pchg_ary_inst[0].uy() - self.min_point_y)
                    
            subank_drv_out_xoff = mod.lx()-(i+1)*self.m_pitch("m1")
            subank_drv_out_yoff = mod.get_pin("out[{0}]".format(i)).lc().y
            self.add_rect(layer="metal2", 
                          offset=(subank_drv_out_xoff, self.min_point_y), 
                          width=self.m2_width, 
                          height=mod.uy()- self.min_point_y + self.m2_width)
                    
            width_go_left = (i+1)*self.m_pitch("m1") + self.subank_dec_drv.width - \
                            self.subank_dec_drv.get_pin("out[{0}]".format(i)).lx()
            self.add_rect(layer="metal1", 
                          offset=(subank_drv_out_xoff, subank_drv_out_yoff-0.5*self.m1_width), 
                          width=width_go_left, 
                          height=self.m1_width)
            self.add_via(self.m1_stack, (subank_drv_out_xoff, subank_drv_out_yoff-0.5*self.m1_width))

            width_go_right = self.x_offset_go[i] - subank_drv_out_xoff
            yoff = self.min_point_y+(i+self.num_ctrl_lines+2)*self.m_pitch("m1")
            self.add_rect(layer="metal1", 
                          offset=(subank_drv_out_xoff,yoff), 
                          width=width_go_right, 
                          height=self.m1_width)
            
            self.add_via(self.m1_stack,(subank_drv_out_xoff, yoff-self.m1_width))
            self.add_via(self.m1_stack,(subank_drv_out_xoff + width_go_right, yoff-self.via_shift("v1")))

            # Connect go signals to control logic
            go_off = self.ctrl_logic_inst.get_pin("go[{0}]".format(i))
            x_off = self.min_point_x-i*self.m_pitch("m1")
            y_off = self.ctrl_logic_inst.by()-(self.num_subanks-i)*self.m_pitch("m1")
            self.add_wire(self.m1_stack,[mod.get_pin("out[{0}]".format(i)).lc(),
                                         (x_off, subank_drv_out_yoff), (x_off,y_off),
                                         (go_off.uc().x, y_off), (go_off.uc().x, go_off.by())])

        # connect pchg signal to subabnk_dec_drv enable
        en_off = self.subank_dec_drv_inst.get_pin("en")
        x_off=self.min_point_x-self.num_subanks*self.m_pitch("m1")
        pos3=self.ctrl_logic_inst.get_pin("pchg").uc()
        self.add_wire(self.m1_stack,[en_off.uc(), (en_off.uc().x, en_off.by()-self.m_pitch("m1")),
                                    (x_off, en_off.by()-self.m_pitch("m1")),
                                    (x_off, self.ctrl_logic_inst.by()),
                                    (pos3.x, self.ctrl_logic_inst.by()), pos3])

        if self.two_level_bank:
            # connect S signal to subank_dec_drv2 enable
            en_off = self.subank_dec_drv_inst2.get_pin("en")
            x_off = self.min_point_x-(4+self.num_subanks)*self.m_pitch("m1")
            y_off = self.addrs_ary_inst.get_pin("S").lc().y
            self.add_wire(self.m1_stack,[en_off.uc(), (en_off.uc().x, en_off.by()-2*self.m_pitch("m1")),
                                        (x_off, en_off.by()-2*self.m_pitch("m1")), (x_off, y_off)])


    def route_split_merge_data(self):
        """ Routing the output of split to w_drv array and output of s_amp array to merge"""

        # connecting Input Data to D inputs of split_array
        for i in range(self.num_subanks):
            x_offset= self.subank_width * i + self.bitcell_ary_off+ self.bitcell_array.xleft_shift
            label_list = ["din", "bm"]
            pin_list = ["D"]
            if self.mask:
                pin_list.append("bm_in")
            for j in range(self.w_size):
                for k in range(len(pin_list)):
                    input_pos = self.d_split_ary_inst[i].get_pin(pin_list[k]+"[{0}]".format(j)).uc() 
                    split_in= vector(input_pos.x, self.d_split_ary_inst[0].by())
                    inp=vector(input_pos.x, self.min_point_y)
                    self.add_path("metal3",(input_pos, inp))
                    self.add_via(self.m2_stack,
                             (split_in.x-0.5*contact.m2m3.width,self.min_point_y))
                    self.add_rect(layer="metal2",
                              offset=(split_in.x-0.5*self.m2_width,self.min_point_y),
                              width=self.m2_width,
                              height=util_ceil(self.m2_minarea/self.m2_width))
                    self.add_layout_pin(text=label_list[k]+"[{0}][{1}]".format(i,j),
                                        layer="metal2", 
                                        offset=vector(inp.x-0.5*self.m2_width,self.min_point_y), 
                                        width=self.m2_width,
                                        height= contact.m2m3.height)
                
                # connecting Output Data to Q output of merge_array
                outp_pos = self.d_merge_array.get_pin("Q[{0}]".format(j)).ll() 
                data_out_position = vector(outp_pos.x + x_offset, self.min_point_y)
                height_data_out = self.d_merge_ary_inst[0].by() - self.min_point_y
                self.add_rect(layer="metal2", 
                              offset=data_out_position, 
                              width=self.m2_width,
                              height= height_data_out)                
                self.add_layout_pin(text="dout[{0}][{1}]".format(i,j),
                                    layer="metal2", 
                                    offset=data_out_position, 
                                    width=self.m2_width,
                                    height= self.m2_width)                
                
                # connecting dout from sens_amp to D input of merge_array
                sa_dout = self.s_amp_ary_inst[i].get_pin("data[{0}]".format(j)).uc()
                dout_merge_inputD = self.d_merge_ary_inst[i].get_pin("D[{0}]".format(j)).uc()
                self.add_path("metal3", [dout_merge_inputD, sa_dout])
        
    def route_data_in_and_data_out(self):
        """ Metal 2 routing of s_amp output data and write drv input data if not two_level_bank"""
                
        # connecting Input Data to data-input of w_drv
        for i in range(self.num_subanks):
            x_offset= self.subank_width * i + self.bitcell_ary_off + self.bitcell_array.xleft_shift
            for j in range(self.w_size):
                wd_din_pos = self.w_drv_ary_inst[i].get_pin("data[{0}]".format(j)).ll() 
                data_in_pos = vector(wd_din_pos.x, self.min_point_y)
                height_data_in = self.w_drv_ary_inst[0].by() - self.min_point_y
                self.add_rect(layer="metal2", 
                                offset=data_in_pos, 
                                width=self.m2_width,
                                height= height_data_in)
                self.add_layout_pin(text="din[{0}][{1}]".format(i,j),
                                    layer="metal2", 
                                    offset=data_in_pos, 
                                    width=self.m2_width,
                                    height= self.m2_width)
                if self.mask:
                    bm_pos = vector(self.w_drv_ary_inst[i].get_pin("bm[{0}]".format(j)).lx(), self.min_point_y)
                    self.add_rect(layer="metal2", 
                                  offset=bm_pos, 
                                  width=self.m2_width,
                                 height= height_data_in)
                    self.add_layout_pin(text="bm[{0}][{1}]".format(i,j),
                                        layer="metal2", 
                                        offset=bm_pos, 
                                        width=self.m2_width,
                                        height= self.m2_width)

                sa_dout_pos = self.s_amp_ary_inst[i].get_pin("data[{0}]".format(j)).ll() 
                data_out_pos = vector(sa_dout_pos.x, self.min_point_y)
                height_data_out = self.s_amp_ary_inst[0].by() - self.min_point_y
                self.add_rect(layer="metal3", 
                                offset=data_out_pos, 
                                width=self.m3_width,
                                height= height_data_out)
                self.add_via(self.m2_stack, (data_out_pos.x-drc["metal3_enclosure_via2"], self.min_point_y))
                self.add_rect(layer="metal2", 
                                offset=data_out_pos, 
                                width=contact.m1m2.width,
                                height= util_ceil(self.m2_minarea/contact.m1m2.width))

                self.add_layout_pin(text="dout[{0}][{1}]".format(i,j),
                                    layer="metal2", 
                                    offset=data_out_pos, 
                                    width=self.m2_width,
                                    height= self.m2_width)

    def route_ctrl_logic(self):
        """ Add and connect ctrl signals (pchg, sen, wen, decoder_enable) to drivers"""

        if not self.two_level_bank:
            ctrl_logic_pins=["reset", "r", "w", "rw", "ack", "rack", "rreq", "wreq", "wack"]
            if self.power_gate:
                ctrl_logic_pins.append("sleep")  
            for i in range(9):
                offset= self.ctrl_logic_inst.get_pin(ctrl_logic_pins[i]).ll()
                self.add_layout_pin(text=ctrl_logic_pins[i],
                                    layer="metal1", 
                                    offset=(offset.x, offset.y), 
                                    width=self.m1_width, 
                                    height=self.m1_width)

        # Route wreq from ctrl logic to write_complete_array
        wreq_pos1= self.w_comp_inst[self.num_subanks-1].get_pin("en").lc()
        wreq_pos2 = vector(self.ctrl_logic_inst.rx()-self.m2_width, wreq_pos1.y)
        self.ctrl_maxy = max(self.row_dec_drv_en.y+self.m_pitch("m2"), self.ctrl_logic_inst.uy())
        y_off = max(wreq_pos1.y, self.ctrl_maxy+2*self.m_pitch("m2"))
        x_off = self.ctrl_logic_inst.lx()-2*self.m_pitch("m1")
        if self.two_level_bank:
            x_off = x_off-util_ceil(self.m2_minarea/contact.m1m2.height)
        
        wreq_pos3 = vector(wreq_pos2.x, self.ctrl_maxy+2*self.m_pitch("m2"))
        wreq_pos4 = vector(x_off, wreq_pos3.y)
        wreq_pos6 = self.ctrl_logic_inst.get_pin("wreq").lc()
        wreq_pos5= vector(x_off,wreq_pos6.y)
        self.add_wire(self.m1_stack, [wreq_pos1,wreq_pos2, wreq_pos3])
        self.add_wire(self.m2_rev_stack, [wreq_pos2, wreq_pos3, wreq_pos4, wreq_pos5])
        self.add_wire(self.m1_stack, [wreq_pos4, wreq_pos5, wreq_pos6])
        
        if abs(wreq_pos2.y-wreq_pos3.y)< (self.m2_minarea/self.m2_width):
            shift = abs(wreq_pos3.y- wreq_pos2.y) + (self.m2_minarea/contact.m1m2.height)
            off = vector(wreq_pos3.x-0.5*contact.m1m2.height, min(wreq_pos2.y, wreq_pos3.y)-0.5*contact.m1m2.width)
            self.add_rect(layer="metal2",
                          offset=off,
                          width= contact.m1m2.height,
                          height= shift)

        # Route decode_enabel from ctrl logic to row_dec_drv_en
        decoder_en_pos1= (self.row_dec_drv_en.x,self.row_dec_drv_en.y-contact.m1m2.width)
        decoder_en_pos3= self.ctrl_logic_inst.get_pin("decoder_enable").uc()
        decoder_en_pos2= (decoder_en_pos3.x,self.ctrl_maxy)
        self.add_wire(self.m2_rev_stack, [decoder_en_pos1, decoder_en_pos2, decoder_en_pos3])

        # Route pchg from ctrl logic to ctrl bus rails (ctrl_lines_orders: "pchg", "sen", "wen"])
        pin_list =["pchg", "sen", "wen"]
        for i in range(len(pin_list)):
            pos1= (self.ctrl_line_xoffset[i]+0.5*self.m2_width, self.row_dec_drv_en.y+(i+1)*self.m_pitch("m2"))
            pos3= self.ctrl_logic_inst.get_pin(pin_list[i])
            pos2= vector(pos3.lx(), self.ctrl_maxy+(3+i)*self.m_pitch("m2"))
            
            off = pos2-vector(self.via_shift("v1"), -0.5*contact.m2m3.width)
            self.add_via(self.m2_stack, off, rotate=270)
            self.add_wire(self.m2_rev_stack, [pos1, pos2])
            self.add_rect(layer="metal2",
                          offset=self.ctrl_logic_inst.get_pin(pin_list[i]).ul(),
                          width= contact.m1m2.width,
                          height= pos2[1] -pos3.uy())

        # Route w_complete  and  data_ready lines from ctrl logic to w_complete and data_ready bus
        for i in range(self.num_subanks):
            pin_list=["write_complete[{0}]".format(i), "data_ready[{0}]".format(i)]
            module=[self.w_complete_xoffset[i], self.data_ready_xoffset[i]]
            for j in range(2):
                off = self.ctrl_logic_inst.get_pin(pin_list[j])
                yoff = self.row_dec_drv_en.y+(i+5+self.num_subanks*j)*self.m_pitch("m2")
                pos1= vector(module[j]+0.5*contact.m2m3.first_layer_height, yoff)
                pos2= vector(off.lx(), self.ctrl_maxy+(i+6+self.num_subanks*j)*self.m_pitch("m2"))
                
                self.add_via(self.m2_stack, pos2-vector(self.via_shift("v1"),-0.5*contact.m2m3.width), rotate=270)
                self.add_wire(self.m2_rev_stack,[pos1, pos2])
                self.add_rect(layer="metal2",
                              offset=off.ul(),
                              width= contact.m1m2.width,
                              height= pos2.y -off.uc().y)
                self.add_rect(layer="metal2",
                              offset=(module[j], pos1.y),
                              width= contact.m2m3.first_layer_height,
                              height= pos2.y -pos1.y)

        # if two_level_bank, ctrl signals go from split/merge array to ctrl logic
        if self.two_level_bank:
            reset_split_input = self.ctrl_logic_inst.get_pin("reset").ll()
            self.add_layout_pin(text="reset",
                                layer="metal1", 
                                offset=reset_split_input, 
                                width=self.m1_width, 
                                height=self.m1_width)

            ctrl_split_pins=["wreq", "rreq", "w", "rw", "r"]
            x_off = self.min_point_x-(self.num_subanks+2*self.num_split_ctrl_lines)*self.m_pitch("m1")
            for i in range(len(ctrl_split_pins)):
                spliti = self.ctrls_ary_inst.get_pin("D[{0}]".format(i))
                y_off= spliti.by()-(i+1)*self.m_pitch("m2")
                self.add_path("metal3", [spliti.uc(), (spliti.uc().x, y_off), (x_off,y_off)])
                self.add_layout_pin(text=ctrl_split_pins[i],
                                    layer="metal3", 
                                    offset=(x_off,y_off-0.5*self.m3_width), 
                                    width=self.m3_width, 
                                    height=self.m3_width)
            
            ctrl_merge_pins=["ack","rack","wack"]
            merge_cells=[self.ack_merge_cell_inst,self.rack_merge_cell_inst,self.wack_merge_cell_inst]
            for i in range(len(ctrl_merge_pins)):
                mergei = merge_cells[i].get_pin("Q[0]")
                y_off= mergei.by()-(i+6)*self.m_pitch("m2")
                self.add_path("metal3", [mergei.uc(), (mergei.uc().x, y_off), (x_off, y_off)])
                self.add_via_center(self.m2_stack,mergei.uc())
                self.add_layout_pin(text=ctrl_merge_pins[i],
                                    layer="metal3",
                                    offset=(x_off,y_off-0.5*self.m3_width),
                                    width=self.m3_width,
                                    height=self.m3_width)

            self.add_layout_pin(text="ack_merge",
                                layer="metal1",
                                offset=self.ctrl_logic_inst.get_pin("ack").ll(),
                                width=self.m1_width,
                                height=self.m1_width)

        if self.power_gate:    
            self.add_layout_pin(text="sleep",
                                layer="metal1",
                                offset=self.ctrl_logic_inst.get_pin("sleep").ll(),
                                width=self.m1_width,
                                height=self.m1_width)

    def route_split_merge_to_ctrl_logic(self):
        """ route output of split/merge cells to ctrl logic """
        
        ctrl_split_pins=["wreq", "rreq", "w", "rw", "r"]
        min_x = self.ctrls_ary_inst.get_pin("Q[0]").uc().x
        if min_x < self.ctrl_logic_inst.lx()-5*self.m_pitch("m2"):
            x_off = min_x
        else:
            x_off = self.ctrl_logic_inst.lx()-5*self.m_pitch("m2")    
        for i in range(len(ctrl_split_pins)):
            rwrw_split_out = self.ctrls_ary_inst.get_pin("Q[{0}]".format(i)).uc()
            rwrw_ctrl_logic_in = self.ctrl_logic_inst.get_pin(ctrl_split_pins[i]).lc()
            mid_pos1=vector(x_off +i*self.m_pitch("m2"), rwrw_ctrl_logic_in.y)
            mid_pos2=vector(mid_pos1.x, rwrw_split_out.y+(i+1)*self.m_pitch("m2"))
            mid_pos3=vector(rwrw_split_out.x, mid_pos2.y)
            
            self.add_path("metal3", [rwrw_ctrl_logic_in, mid_pos1, mid_pos2, mid_pos3, rwrw_split_out])
            self.add_via(self.m2_stack, rwrw_split_out-vector(0.5*self.m3_width, contact.m1m2.height))
            self.add_via_center(self.m2_stack, rwrw_ctrl_logic_in, rotate=90)
            self.add_via_center(self.m1_stack, rwrw_ctrl_logic_in,rotate=90)
            self.add_rect_center(layer="metal2",
                                 offset=(rwrw_ctrl_logic_in.x-self.m2_width, rwrw_ctrl_logic_in.y),
                                 width= util_ceil(self.m2_minarea/contact.m1m2.width),
                                 height=contact.m1m2.width)

        modules = [self.ack_merge_cell_inst,self.wack_merge_cell_inst,self.rack_merge_cell_inst]
        pin_list=["ack", "wack", "rack"]
        for mod in modules:
            merge_output = mod.get_pin("D[0]").uc()
            ctrl_logic_input = self.ctrl_logic_inst.get_pin(pin_list[modules.index(mod)]).lc()
            self.add_path("metal3",[merge_output, ctrl_logic_input])
            self.add_via_center(self.m2_stack, ctrl_logic_input)
            self.add_via_center(self.m1_stack, ctrl_logic_input)
            self.add_rect_center(layer="metal2",
                                 offset=ctrl_logic_input,
                                 width= util_ceil(self.m2_minarea/contact.m1m2.height),
                                 height=2*contact.m1m2.height)
        
        
    def route_ctrl_split_merge_cells(self):
        """ Route input, output and ctrls of split and merge cells if two_level_bank"""

        # Route S, EN1_S, EN2_S and reset pins of ctrl, addr and data_split arrays 
        split_pins = ["en1_S", "en2_S"]
        for i in range(len(split_pins)):
            ctrl_split= self.ctrls_ary_inst.get_pin(split_pins[i]).lc()
            addr_split= self.addrs_ary_inst.get_pin(split_pins[i]).lc()
            
            split_en1_S = min(ctrl_split.x, addr_split.x)
            x_off = self.min_point_x-(i+1+self.num_subanks)*self.m_pitch("m1")
            pos1= vector(x_off, ctrl_split.y)
            pos2= vector(x_off, addr_split.y)
            pos3= vector(x_off, self.min_point_y-self.m_pitch("m1"))
            self.add_wire(self.m1_stack,[ctrl_split, pos1, pos2, addr_split])
            
            for j in range(self.num_subanks):
                din_split = vector(self.split_xoffset[i]+self.subank_width * j,self.min_point_y)
                pos4= vector(din_split.x, self.min_point_y-(i+1)*self.m_pitch("m1"))
                self.add_wire(self.m1_stack,[pos1, pos2, pos3, pos4])
                
                if self.num_subanks>1:
                    self.add_path("metal3",[pos4, din_split])
                    self.add_via_center(self.m1_stack,pos4)
                    self.add_via_center(self.m2_stack,pos4)
                    self.add_rect_center(layer="metal2", 
                                         offset=pos4-vector(0,0.5*self.m_pitch("m1")+self.via_shift("v1")), 
                                         width = contact.m2m3.width, 
                                         height= util_ceil(self.m2_minarea/contact.m2m3.width))
                    
                else:
                    en = self.d_split_ary_inst[j].get_pin(split_pins[i]).lc()
                    pos5= vector(pos4.x, en.y)
                    self.add_wire(self.m1_stack,[pos4, pos5, en])
                    self.add_via_center(self.m1_stack,pos4)


        # Connect reset signal of addr_split array to ctrl_split, din_split and dout_merge array
        ctrl_split= self.ctrls_ary_inst.get_pin("reset").lc()
        addr_split= self.addrs_ary_inst.get_pin("reset").lc()
        din_split = vector(self.split_xoffset[2]+0.5*self.m2_width,
                           self.d_split_ary_inst[0].get_pin("reset").lc().y)
        split_en1_S = min(ctrl_split.x, addr_split.x)
        x_off = self.min_point_x-(3+self.num_subanks)*self.m_pitch("m1")
        pos1= vector(x_off, ctrl_split.y)
        pos2= vector(x_off, addr_split.y)
        pos3= vector(x_off, self.min_point_y-self.m_pitch("m1"))
        self.add_wire(self.m1_stack,[ctrl_split, pos1, pos2, addr_split])
        
        for j in range(self.num_subanks):
            pos5=self.d_split_ary_inst[j].get_pin("reset").lc()
            din_split = vector(self.split_xoffset[2]+self.subank_width*j,pos5.y)
            pos4= vector(din_split.x, self.min_point_y-3*self.m_pitch("m1"))
            pos6=self.d_merge_ary_inst[j].get_pin("reset").lc()
            self.add_wire(self.m1_stack,[pos1, pos2, pos3, pos4, din_split, pos5])
            self.add_wire(self.m1_stack,[pos4, din_split, pos6])

        # Connect S signal of addr_split array to ctrl_split array
        ctrl_split= self.ctrls_ary_inst.get_pin("S").lc()
        addr_split= self.addrs_ary_inst.get_pin("S").lc()
        x_off = self.min_point_x-(4+self.num_subanks)*self.m_pitch("m1")
        pos1= vector(x_off, ctrl_split.y)
        pos2= vector(x_off, addr_split.y)
        self.add_wire(self.m1_stack,[ctrl_split, pos1, pos2, addr_split])

        # Connect S signal of addr_split array to d_split array
        if self.num_subanks==1:
            d_split= self.d_split_ary_inst[0].get_pin("S").lc()
            d_merge= self.d_merge_ary_inst[0].get_pin("M").lc()
            pos3= vector(x_off, self.min_point_y-4*self.m_pitch("m1"))
            pos4= vector(self.split_xoffset[3], pos3.y)
            pos5= vector(pos4.x, d_split.y)
            self.add_wire(self.m1_stack,[pos2, pos3, pos4, pos5, d_split])
            self.add_wire(self.m1_stack,[pos2, pos3, pos4, pos5, d_merge])
        
        split_ctrl_pins=["S", "rw_en1_S", "rw_en2_S"]
        ctrl_pins=["S","en1_S","en2_S"]
        for i in range(len(split_ctrl_pins)):
             x_off=self.min_point_x-(self.num_subanks+2*self.num_split_ctrl_lines)*self.m_pitch("m1")
             width = abs(x_off-self.ctrls_ary_inst.get_pin(ctrl_pins[i]).lc().x)
             off = (x_off,self.ctrls_ary_inst.get_pin(ctrl_pins[i]).by())
             self.add_rect(layer="metal1",
                           offset=off,
                           width=width,
                           height=self.m1_width)
             self.add_layout_pin(text=split_ctrl_pins[i],
                                 layer="metal1",
                                 offset=off,
                                 width=self.m1_width,
                                 height=self.m1_width)
        
        # Route wack, rack and ack merge ctrls EN1_M 
        merge_cells=[self.rack_merge_cell_inst, self.wack_merge_cell_inst, self.ack_merge_cell_inst]
        for i in range(len(merge_cells)):
            mrg_en1_M = merge_cells[i].get_pin("en1_M").lc()
            mrg_en2_M = merge_cells[i].get_pin("en2_M").lc()
            yoff1= merge_cells[i].uy()+(2*i+1)*self.m_pitch("m1")
            yoff2= merge_cells[i].uy()+(2*i+2)*self.m_pitch("m1")
            pos1_en1_M= vector(mrg_en1_M.x-self.m_pitch("m1"), mrg_en1_M.y)
            pos1_en2_M= vector(mrg_en2_M.x-2*self.m_pitch("m1"), mrg_en2_M.y)
            pos2_en1_M= vector(pos1_en1_M.x, yoff1)
            pos2_en2_M= vector(pos1_en2_M.x, yoff2)
            x_off = self.min_point_x-(self.num_subanks+2*self.num_split_ctrl_lines)*self.m_pitch("m1")
            pos3_en1_M= (x_off, yoff1)
            pos3_en2_M= (x_off, yoff2)
            self.add_wire(self.m1_stack, [mrg_en1_M, pos1_en1_M, pos2_en1_M, pos3_en1_M])
            self.add_wire(self.m1_stack, [mrg_en2_M, pos1_en2_M, pos2_en2_M, pos3_en2_M])

        merge_ctrl_pins=["Mrack", "Mwack", "Mack"]
        for i in range(len(merge_ctrl_pins)):
            off = (x_off,self.rack_merge_cell_inst.uy()+(2*i+1)*self.m_pitch("m1")-0.5*self.m1_width)
            self.add_layout_pin(text=merge_ctrl_pins[i],
                                layer="metal1",
                                offset=off,
                                width=self.m1_width,
                                height=self.m1_width)
        
        # Connect en2_M signals from ctrl_merge_cell to ctrl_logic
        merge_cells=[self.rack_merge_cell_inst, self.wack_merge_cell_inst]
        ctrl_pin = ["rreq_merge", "wreq"]
        for i in range(len(merge_cells)):
            mrg_en2_M = vector(self.min_point_x-self.num_subanks*self.m_pitch("m1"), 
                               self.rack_merge_cell_inst.uy()+ (2*i+2)*self.m_pitch("m1")) 
            pos1_en2_M = vector(mrg_en2_M.x-(i+4)*self.m_pitch("m1"),mrg_en2_M.y)
            pos3_en2_M = self.ctrl_logic_inst.get_pin(ctrl_pin[i]).lc()
            pos2_en2_M = vector(pos1_en2_M.x,pos3_en2_M.y)
            self.add_wire(self.m1_stack, [mrg_en2_M, pos1_en2_M, pos2_en2_M, pos3_en2_M])
        
        mrg_en2_M = vector(self.min_point_x-self.num_subanks*self.m_pitch("m1"), 
                           self.rack_merge_cell_inst.uy()+ 6*self.m_pitch("m1")) 
        pos1_en2_M = vector(mrg_en2_M.x-6*self.m_pitch("m1"),mrg_en2_M.y)
        pos2_en2_M = vector(pos1_en2_M.x, self.ctrl_logic_inst.by())
        pos4_en2_M = self.ctrl_logic_inst.get_pin("pchg").uc()
        pos3_en2_M = vector(pos4_en2_M.x, pos2_en2_M.y)
        self.add_wire(self.m1_stack, [mrg_en2_M, pos1_en2_M, pos2_en2_M, pos3_en2_M, pos4_en2_M])

        # Connection all M and reset pins together
        xoff = self.min_point_x-(self.num_subanks+4)*self.m_pitch("m1")
        pos1 = vector(xoff, self.ctrls_ary_inst.get_pin("S").lc().y)
        pos2 = self.wack_merge_cell_inst.get_pin("M").lc()
        self.add_path("metal1", [pos1, pos2])

        pos1 = vector(pos1.x+self.m_pitch("m1"), self.ctrls_ary_inst.get_pin("reset").lc().y)
        pos2 = self.wack_merge_cell_inst.get_pin("reset").lc()
        self.add_path("metal1", [pos1, pos2])
        
        # Connection of reset and select between split and merge controls and contrl_logic
        pos1 = vector(pos1.x, self.wack_merge_cell_inst.get_pin("reset").lc().y)
        pos3 = self.ctrl_logic_inst.get_pin("reset").lc()
        pos2 = vector(pos1.x, pos3.y)
        self.add_wire(self.m1_stack, [pos1, pos2, pos3])
                    
        for j in range(self.num_subanks):
            dout_mrg_en1_M = vector(self.merge_xoffset[0]+self.subank_width*j, self.min_point_y)
            dout_mrg_en2_M = vector(self.merge_xoffset[1]+self.subank_width*j, self.min_point_y)

            # Connect input of signal from rack_merge_cell to en1_M of data_out_merge_array
            x_off = self.min_point_x-self.num_subanks*self.m_pitch("m1")
            pos1= self.rack_merge_cell_inst.get_pin("D[0]").uc()
            pos2= vector(x_off-5*self.m_pitch("m1"), pos1.y)
            pos3= vector(pos2.x, self.min_point_y-5*self.m_pitch("m1"))
            pos4= vector(dout_mrg_en1_M.x, pos3.y)
            self.add_wire(self.m1_stack, [pos1, pos2, pos3, pos4])
            self.add_via_center(self.m1_stack, pos1)
            
            if self.num_subanks>1:
                self.add_path("metal3",[pos4, dout_mrg_en1_M])
                self.add_via_center(self.m1_stack,pos4)
                self.add_via_center(self.m2_stack,pos4)
                self.add_rect_center(layer="metal2", 
                                     offset=pos4, 
                                     width=contact.m2m3.width, 
                                     height=util_ceil(self.m2_minarea/contact.m2m3.width))
            else:
                en = self.d_merge_ary_inst[j].get_pin("en1_M").lc()
                pos5= vector(pos4.x, en.y)
                self.add_wire(self.m1_stack,[pos4, pos5, en])
                self.add_via_center(self.m1_stack,pos4)
        
            pos3= vector(x_off-6*self.m_pitch("m1"), self.min_point_y-6*self.m_pitch("m1"))
            pos4= vector(dout_mrg_en2_M.x, pos3.y)
            self.add_wire(self.m1_stack, [pos3, pos4])
            if self.num_subanks>1:
                self.add_path("metal3",[pos4, dout_mrg_en2_M])
                self.add_via_center(self.m1_stack,pos4)
                self.add_via_center(self.m2_stack,pos4)
                self.add_rect_center(layer="metal2", 
                                     offset=pos4, 
                                     width=contact.m2m3.width, 
                                     height=util_ceil(self.m2_minarea/contact.m2m3.width))
            else:
                en = self.d_merge_ary_inst[j].get_pin("en2_M").lc()
                pos5= vector(pos4.x, en.y)
                self.add_wire(self.m1_stack,[pos4, pos5, en])
                self.add_via_center(self.m1_stack,pos4)

        self.add_layout_pin(text="Mdout",
                            layer="metal1",
                            offset=pos3-vector(0, 0.5*self.m1_width),
                            width=self.m1_width,
                            height=self.m1_width)
    
    def route_power(self):
        """ Route vdd/gnd of all modules to fat vertical Vdd/GND in metal2"""
        
        pow_pins = ["vdd", "gnd"]
        offsets1 = [self.vdd_x_offset, self.gnd_x_offset]
        offsets2 = [self.vdd2_x_offset, self.gnd2_x_offset]
        shift = contact.m1m2.width

        for k in range(2):
            for i in range(self.num_subanks):
                inst_list= [self.cell_ary_inst[i], self.s_amp_ary_inst[i], 
                            self.w_drv_ary_inst[i], self.w_comp_inst[i]]
                if pow_pins[k] == "vdd":
                    inst_list.extend([self.pchg_ary_inst[i]])
                if self.two_level_bank:
                    inst_list.extend([self.d_split_ary_inst[i], self.d_merge_ary_inst[i]]) 
                if (self.w_per_row >1 and pow_pins[k] == "gnd"): 
                    inst_list.extend([self.mux_ary_inst[i]])
                
                inst2_list= [self.data_ready_inst[i]] 
                if self.num_subanks>1:
                    inst2_list.extend([self.go_drv_inst[i], self.bitcell_ary_drv_inst[i], 
                                       self.pchg_drv_inst[i]])  
            
                for inst in inst_list :
                    for pin in inst.get_pins(pow_pins[k]):
                        if pin.layer[0:6] == "metal3":
                            layer = "metal3"
                            stack = self.m2_stack
                            height = contact.m2m3.width
                        else:
                            layer = "metal1"
                            stack = self.m1_stack
                            height = contact.m1m2.width
                        
                        self.add_rect(layer=layer, 
                                      offset=pin.ll(), 
                                      width=offsets2[k][i]- pin.lx()+self.m1_width, 
                                      height=height)
                        off = (offsets2[k][i]+0.5*self.pow_width, pin.lc().y)
                        self.add_via_center(stack,off,rotate=270, size=[1, self.num_via])
            
                for inst in inst2_list :
                    for pin in inst.get_pins(pow_pins[k]):
                        if pin.layer[0:6] == "metal3":
                            layer = "metal3"
                            stack = self.m2_stack
                            height = contact.m2m3.width
                        else:
                            layer = "metal1"
                            stack = self.m1_stack
                            height = contact.m1m2.width
                        self.add_rect(layer=layer, 
                                      offset=pin.ll(), 
                                      width=offsets1[k][i]- pin.lx()+self.m1_width, 
                                      height=height)
                        off = (offsets1[k][i], pin.by()+shift)
                        self.add_via(stack, off, rotate=270, size=[1, self.num_via])

        # connect S/M inputs of split/merge go drivers to Vdd
        for i in range(self.num_subanks):
            if (self.two_level_bank and self.num_subanks>1):
                if self.w_per_row>1:
                    index = self.w_per_row
                else:
                    index=0
                for k in range(2):
                    vdd_pin = self.go_drv_inst[i].get_pin("in[{0}]".format(index+4+3*k))
                    self.add_rect(layer="metal1", 
                                  offset=vdd_pin.ll(), 
                                  width=self.vdd_x_offset[i]- vdd_pin.lx()+self.m1_width, 
                                  height=height)
                    off = (self.vdd_x_offset[i], vdd_pin.by()+shift)
                    self.add_via(self.m1_stack, off, rotate=270, size=[1, self.num_via])

            # If there is no write_masking, connect bm pins of write complete and write driver to Vdd
            if not self.mask:
                pin_list = [self.w_drv_ary_inst[i].get_pin("bm[0]"), self.w_comp_inst[i].get_pin("bm")]
                for pin in pin_list:
                    self.add_rect(layer="metal1", 
                                  offset=pin.ll(), 
                                  width=self.vdd2_x_offset[i]- pin.lx()+self.m1_width, 
                                  height=contact.m1m2.width)
                    off = (self.vdd2_x_offset[i], pin.by()+shift)
                    self.add_via(self.m1_stack, off, rotate=270, size=[1, self.num_via])
        
        # Route vdd,gnd for the row decoder
        row_dec_vdd_xoff=self.min_x_row_dec-(self.pow_width+self.m_pitch("m1"))
        row_dec_gnd_xoff=self.min_x_row_dec-2*(self.pow_width+self.m_pitch("m1"))
        offsets = [row_dec_vdd_xoff, row_dec_gnd_xoff]
        
        for i in range(2):
            self.add_rect(layer="metal2", 
                          offset=(offsets[i], self.min_point_y), 
                          width=self.pow_width, 
                          height=self.power_height)
            self.add_layout_pin(text=pow_pins[i],
                                layer="metal2", 
                                offset=(offsets[i], self.min_point_y), 
                                width=self.pow_width, 
                                height=self.pow_width)
 
        inst_list= [self.row_dec_drv_inst, self.row_dec_inst]
        for inst in inst_list:
            for i in range(2):
                for pin in inst.get_pins(pow_pins[i]):
                    if pin.layer[0:6] == "metal3":
                        layer = "metal3"
                        stack = self.m2_stack
                        height = contact.m2m3.width
                    else:
                        layer = "metal1"
                        stack = self.m1_stack
                        height = contact.m1m2.width
                    self.add_rect(layer=layer, 
                                  offset=pin.ll(), 
                                  width=offsets[i]- pin.lx(), 
                                  height=height)
                    off = (offsets[i], pin.by()+shift)
                    self.add_via(stack, off, rotate=270, size=[1, self.num_via])

        # Route vdd, gnd for the col_mux decoder
        if self.mux_addr_size > 0:
            for i in range(2):
                for pin in self.mux_dec_inst.get_pins(pow_pins[i]):
                    if pin.layer[0:6] == "metal3":
                        layer = "metal3"
                        stack = self.m2_stack
                        height = contact.m2m3.width
                    else:
                        layer = "metal1"
                        stack = self.m1_stack
                        height = contact.m1m2.width
                    
                    self.add_rect(layer=layer, 
                                  offset=pin.ll(), 
                                  width=offsets[i]- pin.lx(), 
                                  height=height)
                    off = (offsets[i], pin.by()+shift)
                    self.add_via(stack, off, rotate=270, size=[1, self.num_via])

        # Route vdd, gnd for the subank decoder and column_decoder_drv
        if self.subank_addr_size > 0:
            heighty = self.subank_dec_drv_inst.uy()- self.min_point_y + self.m2_width
            for i in range(2):
                xshift = (self.num_subanks+1+i)*self.m_pitch("m1")
                subank_dec_xoff=self.subank_dec_drv_inst.lx() - xshift
                if self.two_level_bank:
                    subank_dec_xoff=self.subank_dec_drv_inst2.lx() - xshift
                
                self.add_rect(layer="metal2", 
                              offset=(subank_dec_xoff, self.min_point_y), 
                              width=self.m2_width, 
                              height=heighty)
                
                for pin in self.subank_dec_drv_inst.get_pins(pow_pins[i]):
                    self.add_rect(layer="metal1", 
                                  offset=pin.ll(), 
                                  width=subank_dec_xoff- pin.lx(), 
                                  height=self.m1_width)
                    self.add_via(layers=self.m1_stack, offset=(subank_dec_xoff, pin.by()))
                
                off = (subank_dec_xoff, self.min_point_y+(1-i)*self.m_pitch("m1"))
                self.add_rect(layer="metal1", 
                              offset=off, 
                              width=offsets[i]-subank_dec_xoff, 
                              height=self.m2_width)
                
                yoff=self.min_point_y+(1-i)*self.m_pitch("m1")-self.via_shift("v1")
                self.add_via(self.m1_stack,(subank_dec_xoff,yoff))
                self.add_via(self.m1_stack,(offsets[i],yoff), size=[self.num_via,1])

        # Route vdd,gnd for the address/ctrl splits & merge  if two_level_bank to ctrl_logic vdd,gnd
        if self.two_level_bank:
            for i in range(2):
                ctrl_mrg_off=self.wack_merge_cell_inst.get_pin(pow_pins[i]).lc()
                addr_spl_off=self.addrs_ary_inst.get_pin(pow_pins[i]).lc()
                x_off = self.min_point_x-(self.num_subanks+8-i)*self.m_pitch("m1")
                pos1= vector(x_off, ctrl_mrg_off.y)
                pos2= vector(x_off, addr_spl_off.y)
                self.add_wire(self.m1_stack, [ctrl_mrg_off, pos1])
                self.add_wire(self.m1_stack, [ctrl_mrg_off, pos1, pos2, addr_spl_off])

                y_off = self.ctrl_logic_inst.by()-(self.num_subanks+2-i)*self.m_pitch("m1")
                pos3= vector(x_off,y_off)
                pos5= self.ctrl_logic_inst.get_pin(pow_pins[i]).uc()
                pos4= vector(pos5.x,y_off)
                self.add_wire(self.m1_stack, [ctrl_mrg_off, pos1, pos3, pos4, pos5])

        # Route vdd,gnd from ctrl logic to vdd,gnd rail
        for i in range(2):
            yoff1 = self.row_dec_drv_inst.uy()+(6+i+2*self.num_subanks)*self.m_pitch("m2")
            ctrl_yoff = max (yoff1, self.ctrl_maxy + (7+i+self.num_subanks*2)*self.m_pitch("m2"))
            pos1= vector(offsets[i]+0.5*self.pow_width, ctrl_yoff)
            pos2= vector(pos1.x, yoff1)
            pos3= vector(self.ctrl_logic_inst.get_pin(pow_pins[i]).uc().x, ctrl_yoff)
            pos4= self.ctrl_logic_inst.get_pin(pow_pins[i]).uc()
            self.add_path("metal2",[(pos1[0],pos1[1]+contact.m2m3.width) , pos2], width=self.pow_width)
            self.add_path("metal2",[pos3, pos4])
            self.add_path("metal3",[(pos2.x, max(pos2.y, pos1.y)), pos3])
            self.add_via_center(self.m2_stack, pos3)
            self.add_via_center(self.m2_stack, (pos2.x, max(pos2.y, pos1.y)), size=[self.num_via,1])
