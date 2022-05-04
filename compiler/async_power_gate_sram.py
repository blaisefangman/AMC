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
from globals import OPTS, print_time
import design
import debug
import utils
import contact
from vector import vector
from math import floor, log, ceil
from tech import GDS,layer, drc
from async_nor2 import nor2
from async_pinv import pinv
from async_delay_chain import delay_chain
from async_sram import sram
from async_power_gate_cell import power_gate_cell
from utils import ceil as util_ceil

class power_gate_sram(design.design):
    """
    This module implements the a power gated sram module."""

    def __init__(self, word_size, words_per_row, num_rows, num_subanks,   
                 branch_factors, bank_orientations, mask, name):
        design.design.__init__(self, name)
        debug.info(2, "Create power gated sram")

        self.word_size = word_size
        self.w_per_row = words_per_row
        self.num_subanks = num_subanks
        self.num_rows = num_rows
        self.branch_factors = branch_factors
        self.bank_orientations = bank_orientations
        self.mask = mask
        self.num_outbanks = branch_factors[0]
        self.num_inbanks = branch_factors[1]
        self.power_gate = True
        
        #even number
        self.buf_size = 6
        self.size=self.pmos_group_size = 10
       
        self.addr_size= int(log(self.num_rows, 2)+log(self.num_subanks, 2)+log(self.w_per_row, 2)+ \
                            log(self.branch_factors[0], 2) + log(self.branch_factors[1], 2))
        self.total_bits = self.num_rows*self.num_subanks*self.word_size*\
                          self.w_per_row*self.num_inbanks*self.num_outbanks
        

        self.strap_w = 2*self.m1_pitch
        via_pitch = drc["minwidth_via1"]+drc["via1_to_via1"]
        self.num_via = int(ceil((self.strap_w+drc["via1_to_via1"]-2*drc["m1_extend_via1"]) / via_pitch))
        via1=contact.contact(layer_stack=("m1", "via1", "m2"), dimensions=[1,self.num_via])
        via2=contact.contact(layer_stack=("m2", "via2", "m3"), dimensions=[1,self.num_via])
        self.strap_w = max(via1.height, via2.height)
        self.gap = max(self.well_space, 2*self.m2_pitch)
        
        self.add_pins()
        self.create_modules()
        self.add_modules()
        
        self.width=2*self.vstrap_w+self.sram_mod.width
        self.height=2*self.hstrap_h+self.sram_mod.height
        self.offset_all_coordinates()
        
    def add_pins(self):
        
        for i in range(self.word_size):
                self.add_pin("data_in[{0}]".format(i),"INPUT")
        for i in range(self.word_size):
                self.add_pin("data_out[{0}]".format(i),"OUTPUT")
        for i in range(self.addr_size):
            self.add_pin("addr[{0}]".format(i),"INPUT")
        if self.mask:
            for i in range(self.word_size):
                self.add_pin("bm[{0}]".format(i),"INPUT")
        self.add_pin_list(["reset", "r", "w",  "rw"],"INPUT")
        self.add_pin_list(["ack", "rack"], "OUTPUT")
        self.add_pin_list(["rreq", "wreq"],"INPUT")
        self.add_pin_list(["wack"],"OUTPUT")
        self.add_pin_list(["sleep"],"INPUT")
        self.add_pin("vdd","POWER")
        self.add_pin("gnd","GROUND")

    def create_modules(self):
    
        self.pg = power_gate_cell()
        self.add_mod(self.pg)
        
        self.dc1 = delay_chain(num_inv=self.buf_size, num_stage=1, name="dc1_power")
        self.add_mod(self.dc1)
        self.dc2 = delay_chain(num_inv=self.buf_size, num_stage=self.buf_size, name="dc2_power")
        self.add_mod(self.dc2)

        self.sram_mod = sram(self.word_size, self.w_per_row, self.num_rows, self.num_subanks, 
                             self.branch_factors, self.bank_orientations, self.mask, 
                             power_gate= True, name="not_power_gated_sram")
        self.add_mod(self.sram_mod)
    
    def setup_layout_constants(self):
        
        """  calculating the area to place the sleep transistors.
             Sleep transistors are not allowed at the place of input and output ports"""

        if self.branch_factors[0]>1:
            self.ytop2 = self.ytop = self.sram_inst.get_pin("r").uy()
            self.ybot = self.sram_inst.get_pin("gnd").by()
            self.xleft=self.sram_inst.lx()
            self.xright=self.sram_inst.lx()

        else:
            if self.branch_factors[1]>1:
                self.ybot = self.sram_inst.get_pin("data_in[0]").by()
                self.ytop2=self.ytop = self.sram_inst.get_pin("data_out[{}]".format(self.word_size-1)).uy()+\
                                       (2*self.word_size+10)*self.m1_pitch
                self.xleft=self.sram_inst.get_pin("sleep").lx()-self.m1_pitch
                self.xright=self.sram_inst.get_pin("r").rx()
            else:
                self.ybot = self.sram_inst.get_pin("data_in[0]").by()
                self.ytop2=self.ytop = self.sram_inst.get_pin("sleep").uy()
            
                self.xleft=self.sram_inst.lx()
                self.xright=self.sram_inst.get_pin("addr[{0}]".format(self.addr_size-1)).rx()

        self.left_side = self.xleft- self.sram_inst.lx()
        self.right_side = self.sram_inst.rx()-self.xright
        self.bot_side = self.ybot - self.sram_inst.by()
        if (self.bank_orientations[0]=="V" and self.bank_orientations[1]=="V"):
            self.bot_side = self.bot_side - self.word_size*self.m1_pitch
        self.top_side = self.sram_inst.uy() - self.ytop
        
        mod_width = self.pg.width*self.size + self.dc2.width + self.gap
        self.lh_pmos = max(int(floor(self.left_side / mod_width)), 0)
        self.rh_pmos = max(int(floor(self.right_side / mod_width)), 0)
        self.mh_pmos = max(int(floor(self.sram_mod.width / mod_width)), 0)
        
        mod_height = self.pg.height*self.size+ self.dc1.height + 3*self.gap
        self.tv_pmos = max(int(floor(self.top_side /mod_height)), 0)
        self.bv_pmos = max(int(floor(self.bot_side /mod_height)), 0)
    
    def add_straps(self):
        """ add horizontal straps in Metal3 and vertical straps in Metal2 """
        
        #Horizontal Metal3 rails at TOP and BOTTOM
        for i in range(2):
            for j in range(2):
                yoff=0.5*self.strap_p+abs(j-i)*(self.hstrap_h-self.strap_p)+ \
                     i*(self.sram_inst.height+self.hstrap_h)
                pos1=vector(j*(self.vstrap_w-self.strap_p), yoff)
                pos2=vector(2*self.vstrap_w+self.sram_inst.width-j*self.vstrap_w+j*self.strap_p, yoff)
                self.add_path("m3", [pos1, pos2], width=self.strap_w)
                if j==0:
                    self.add_layout_pin(text="vdd", layer="m3", 
                                        offset=pos1-vector(0, 0.5*self.strap_w), 
                                        width=pos2.x-pos1.x, height=self.strap_w)
        
        #Vertical Metal2 rails at LEFT and RIGHT
        self.v_rail_pos=[]
        for i in range(2):
            for j in range(2):
                xoff=0.5*self.strap_p+abs(j-i)*(self.vstrap_w-self.strap_p)+ \
                     i*(self.sram_inst.width+self.vstrap_w)
                self.v_rail_pos.append(xoff)
                pos1=(xoff, j*(self.hstrap_h-self.strap_p))
                pos2=(xoff, 2*self.hstrap_h+self.sram_inst.height-j*(self.hstrap_h-self.strap_p))
                self.add_path("m2", [pos1, pos2], width=self.strap_w)

        
        for i in range(2):
            for j in range(2):
                yshift = j%2*(self.hstrap_h-self.strap_p)
                if j%2:
                    shift= -(i%2)*(self.vstrap_w-self.strap_p)
                else:
                    shift= i%2*(self.vstrap_w-self.strap_p)

                xshift = j%2*(self.vstrap_w-self.strap_p)+ shift
                xoff=0.5*self.strap_p+xshift+i*(self.sram_inst.width+self.vstrap_w)
                yoff1=0.5*self.strap_p+yshift
                yoff2= yoff1+self.sram_inst.height+2*self.hstrap_h-self.strap_p-2*yshift
                self.add_via_center(self.m2_stack, (xoff, yoff1), size=[self.num_via, self.num_via])
                self.add_via_center(self.m2_stack, (xoff, yoff2), size=[self.num_via, self.num_via])
    
        #connect vvdd of sram module to vvdd straps
        for i in range(len(self.sram_inst.get_pins("vdd"))):
            pos=self.sram_inst.get_pins("vdd")[i]
            self.add_path("m3", [(pos.lx(), pos.lc().y), (self.sram_inst.lx()-self.strap_p, pos.lc().y)], width=pos.height())
            self.add_path("m3", [(pos.rx(), pos.lc().y), (self.sram_inst.rx()+self.strap_p, pos.lc().y)], width=pos.height())
            self.add_via_center(self.m2_stack, (self.sram_inst.lx()-0.5*self.strap_p, pos.lc().y), size=[self.num_via, self.num_via])
            self.add_via_center(self.m2_stack, (self.sram_inst.rx()+0.5*self.strap_p, pos.lc().y), size=[self.num_via, self.num_via])
        
        
    def add_modules(self):
        
        self.strap_p = self.strap_w + 4*self.m2_pitch
        self.vstrap_w= 2*self.strap_p + max(self.pg.width, self.dc1.width)+ 2*self.m1_pitch
        self.hstrap_h=  2*self.strap_p + self.pg.height
    
        self.sram_inst=self.add_inst(name="power_gated_sram",mod=self.sram_mod, offset=(self.vstrap_w,self.hstrap_h))

        temp=[]
        for i in range(self.word_size):
                temp.append("data_in[{0}]".format(i))
        for i in range(self.word_size):
                temp.append("data_out[{0}]".format(i))
        for i in range(self.addr_size):
            temp.append("addr[{0}]".format(i))
        if self.mask:
            for i in range(self.word_size):
                temp.append("bm[{0}]".format(i))
        temp.extend(["reset", "r", "w",  "rw", "ack", "rack", 
                     "rreq", "wreq", "wack", "sleep", "vvdd", "gnd"])
        self.connect_inst(temp)
        
        pin_list=[]
        if self.num_inbanks!=1:
            for i in range(self.word_size):
                pin_list.append("data_in[{0}]".format(i))
                pin_list.append("data_out[{0}]".format(i))
                if self.mask:
                    pin_list.append("bm[{0}]".format(i))
        
        elif self.num_subanks != 1:
            for i in range(self.word_size):
                pin_list.append("data_in[{0}]".format(i))
                pin_list.append("data_out[{0}]".format(i))
                if self.mask:
                    pin_list.append("bm[{0}]".format(i))

        else:
            pass
        
        if self.sram_inst.get_pin("r").layer[0:2] == "m1":
            for i in range(self.addr_size):
                pin_list.append("addr[{0}]".format(i))
            pin_list.extend(["reset", "r", "w",  "rw", "ack", "rack", "rreq", "wreq", "wack", "sleep"])
        
        for i in pin_list:
            for pin in self.sram_inst.get_pins(i):
                off=vector(0,pin.by())
                width=pin.lx()+self.m1_width
                if i[0:2] == "bm":
                    self.add_rect(layer="m3", offset=off, width=width, height=pin.height())
                else:
                    self.add_rect(layer="m1", offset=off, width=width, height=pin.height())
                self.add_layout_pin(text=i, layer=pin.layer, offset=off, width=width, height=pin.height())
        
        for pin in self.sram_inst.get_pins("gnd"):
            off=vector(0,pin.by())
            width=self.sram_inst.width
            self.add_rect(layer="m3", offset=off, width=width, height=pin.height())
            self.add_layout_pin(text="gnd", layer=pin.layer, offset=off, width=width, height=pin.height())
        
        
        if self.sram_inst.get_pin("r").layer[0:2] == "m2":
            pin_list2=[]
            for i in range(self.addr_size):
                pin_list2.append("addr[{0}]".format(i))
            pin_list2.extend(["reset", "r", "w",  "rw", "ack", "rack", "rreq", "wreq", "wack"])
            if self.num_inbanks > 1:
                pin_list2.extend(["sleep"])
            
            if (self.num_inbanks==1 and self.num_subanks == 1):
                for i in range(self.word_size):
                    pin_list2.append("data_in[{0}]".format(i))
                    pin_list2.append("data_out[{0}]".format(i))
                    if self.mask:
                        pin_list2.append("bm[{0}]".format(i))

            for i in pin_list2:
                pin = self.sram_inst.get_pin(i)
                off=vector(pin.lx(), 0)
                height=pin.by()
                self.add_rect(layer=pin.layer, offset=off, width=pin.width(), height=height)
                self.add_layout_pin(text=i, layer=pin.layer, offset=off, width=pin.width(), height=height)
        
        if self.num_inbanks == 1:
            pin= self.sram_inst.get_pin("sleep")
            width=pin.width()+self.vstrap_w         
            self.add_rect(layer=pin.layer, offset=(0,pin.by()), width=width, height=pin.height())
            self.add_layout_pin(text="sleep", layer=pin.layer, offset=(0,pin.by()), width=width, height=pin.height())

        self.setup_layout_constants()
        self.add_straps()
        self.add_sleep_tx()
        
    def add_sleep_tx(self):
        """  Adding sleep PMOS tx in allowed region + inserting buffer for sleep signal"""
    
        self.pmos_grp_h=self.size*self.pg.height
        
        #order of following loops is important
        #TOP
        xshift=0.5*(self.strap_p+self.pg.height)
        self.gnd_ypos = None
        for i in range(self.mh_pmos):
            xpos = self.vstrap_w+i*(self.size*self.pg.width+self.dc2.width+self.gap)
            ypos=self.strap_p+self.sram_inst.height+self.hstrap_h
            self.dc_inst = self.add_inst(name="dc2_T{}".format(i), mod=self.dc2, offset=vector(xpos, ypos))
            index=i
            if i==0:
                self.connect_inst(["sleep", "sleep{}".format(index), "vdd", "gnd"])
                self.cnt_sleep_pin()
            else:
                self.connect_inst(["sleep{}".format(index-1), "sleep{}".format(index), "vdd", "gnd"])
            if i>0 and i<self.mh_pmos:
                pin = self.pmos_inst[self.size-1].get_pin("sleep")
                self.add_path("m1", [(self.pmos_inst[self.size-1].rx(), pin.uc().y), self.dc_inst.get_pin("in").lc()])
            self.create_pmos_group(orien="H", pos=vector(xpos+self.dc2.width, ypos+0.5*contact.m1m2.width), num=index)
            self.cnt_pmos_hstrap(vvddshift=-xshift, vddshift=-xshift)
            self.cnt_pmos_hsleep(index=0)
            self.cnt_hbuffer_power(pin="vdd", index=self.size-1, direction="r")
            self.cnt_hbuffer_power(pin="gnd", index=self.size-1, direction="r")
            self.gnd_ypos = self.dc_inst.get_pin("gnd").lc().y
            self.gnd_xpos = None
        
        #RIGHT
        xpos=self.sram_inst.width+self.vstrap_w+self.strap_p
        for i in range(self.tv_pmos):
            ypos = self.sram_inst.uy()-i*(self.pmos_grp_h+self.dc1.height+3*self.gap)
            self.dc_inst = self.add_inst(name="dc1_RT{}".format(i), mod=self.dc1, offset=vector(xpos, ypos), mirror="MX")
            index=i+self.mh_pmos
            self.connect_inst(["sleep{}".format(index-1), "sleep{}".format(index), "vdd", "gnd"])
            if i==0:
                self.cnt_corner_sleep(index=self.size-1, direction="h")
            if i>0 and i<self.tv_pmos:
                self.cnt_buffer_vsleep(self.pmos_inst[0])

            self.cnt_vbuffer_vdd()
            self.create_pmos_group(orien="V", pos=vector(xpos, ypos-self.dc1.height-self.pmos_grp_h-self.gap-contact.m1m2.width), num=index)
            self.cnt_pmos_vstrap()
            self.cnt_pmos_vsleep(mod=self.pmos_inst[0])
            self.cnt_vbuffer_gnd(index=0, direction="d")
            self.gnd_xpos=self.dc_inst.get_pin("gnd").lx()-2*self.m1_pitch

        for i in range(self.bv_pmos):
            ypos = self.ybot-i*(self.pmos_grp_h+self.dc1.height+3*self.gap)
            self.dc_inst = self.add_inst(name="dc1_RB{}".format(i), mod=self.dc1, offset=vector(xpos, ypos), mirror="MX")
            index=i+self.tv_pmos+self.mh_pmos
            self.connect_inst(["sleep{}".format(index-1), "sleep{}".format(index), "vdd", "gnd"])
            if i==0:
                if self.gnd_xpos != None:
                    self.cnt_corner_sleep(index=self.size-1, direction="v")
            if i>0 and i<self.bv_pmos:
                self.cnt_buffer_vsleep(self.pmos_inst[0])

            self.cnt_vbuffer_vdd()
            self.create_pmos_group(orien="V", pos=vector(xpos, ypos-self.dc1.height-self.pmos_grp_h-self.gap-contact.m1m2.width), num=index)
            self.cnt_pmos_vstrap()
            self.cnt_pmos_vsleep(mod=self.pmos_inst[0])
            self.cnt_vbuffer_gnd(index=0, direction="d")
            self.gnd_xpos=self.dc_inst.get_pin("gnd").lx()-2*self.m1_pitch

        #BOTTOM
        self.gnd_ypos = None
        for i in range(self.rh_pmos):
            xpos = self.sram_inst.rx()-i*(self.size*self.pg.width+self.dc2.width+self.gap)
            ypos=self.strap_p
            index=i+self.tv_pmos+self.mh_pmos+self.bv_pmos
            self.dc_inst = self.add_inst(name="dc2_BR{}".format(i), mod=self.dc2, offset=vector(xpos, ypos), mirror="MY")
            self.connect_inst(["sleep{}".format(index-1), "sleep{}".format(index), "vdd", "gnd"])
            if i==0:
                if self.gnd_xpos != None:
                    self.cnt_corner_sleep(index=0, direction="v")
                if (self.tv_pmos + self.bv_pmos) == 0:
                    self.cnt_sleep_pin2()
            
            if (i>0 and i<self.rh_pmos):
                pos1= self.pmos_inst[0].get_pin("sleep").lc()
                pos2= (pos1.x-self.m1_width, pos1.y)
                pos3= self.dc_inst.get_pin("in").lc()
                self.add_path("m1", [pos1,pos2,pos3])

            self.create_pmos_group(orien="H", pos=vector(xpos-self.dc2.width-self.size*self.pg.width, ypos+0.5*contact.m1m2.width), num=index)
            self.cnt_pmos_hstrap(vvddshift=xshift, vddshift=xshift)
            self.cnt_pmos_hsleep(index=self.size-1)
            self.cnt_hbuffer_power(pin="vdd",index=0, direction="l")
            self.cnt_hbuffer_power(pin="gnd",index=0, direction="l")
            self.gnd_ypos = self.dc_inst.get_pin("gnd").lc().y
        
        for i in range(self.lh_pmos):
            xpos = self.xleft-i*(self.size*self.pg.width+self.dc2.width+self.gap)
            ypos=self.strap_p
            index=i+self.tv_pmos+self.mh_pmos+self.bv_pmos+self.lh_pmos
            self.dc_inst = self.add_inst(name="dc2_BL{}".format(i), mod=self.dc2, offset=vector(xpos, ypos), mirror="MY")
            self.connect_inst(["sleep{}".format(index-1), "sleep{}".format(index), "vdd", "gnd"])
            if i==0:
                if (self.gnd_ypos != None and self.gnd_xpos!=None):
                    pos1= self.pmos_inst[0].get_pin("sleep").lc()
                    pos2= (pos1.x-self.m1_width, pos1.y)
                    pos3= self.dc_inst.get_pin("in").lc()
                    self.add_path("m1", [pos1,pos2,pos3])
            
            if (i>0 and i<self.lh_pmos):
                pos1= self.pmos_inst[0].get_pin("sleep").lc()
                pos2= (pos1.x-self.m1_width, pos1.y)
                pos3= self.dc_inst.get_pin("in").lc()
                self.add_path("m1", [pos1,pos2,pos3])

            self.create_pmos_group(orien="H", pos=vector(xpos-self.dc2.width-self.size*self.pg.width, ypos+0.5*contact.m1m2.width), num=index)
            self.cnt_pmos_hstrap(vvddshift=xshift, vddshift=xshift)
            self.cnt_pmos_hsleep(index=self.size-1)
            self.cnt_hbuffer_power(pin="vdd",index=0, direction="l")
            self.cnt_hbuffer_power(pin="gnd",index=0, direction="l")
            self.gnd_ypos = self.dc_inst.get_pin("gnd").lc().y
    
    def cnt_vbuffer_vdd(self):
         """ connect the vdd ports of sleep buffers to vdd strap"""
         pin = self.dc_inst.get_pin("vdd")
         pos = vector(self.v_rail_pos[2], pin.lc().y)
         self.add_path("m1", [pin.lc(), pos])
         self.add_via_center(self.m1_stack, pos, size=[self.num_via, 1])
    
    def cnt_hbuffer_power(self, pin, index, direction):
         """ connect the gnd ports of sleep buffers to gnd strap"""
         pin = self.dc_inst.get_pin(pin)
         
         if direction=="r":
              xpos1=self.dc_inst.lx()
              xpos2=self.v_rail_pos[3]
         else:
              xpos1=self.dc_inst.rx()
              xpos2=self.v_rail_pos[1]
         pos1 = vector(xpos1, pin.lc().y)
         pos2 = vector(xpos2, pin.lc().y)
         self.add_path("m1", [pos1, pos2], width=pin.height())
    
    def cnt_vbuffer_gnd(self, index, direction):
         """ connect the vdd ports of sleep buffers to vdd strap"""
         
         pin = self.dc_inst.get_pin("gnd")
         if direction == "u":
             ypos=self.pmos_inst[index].uy()+self.gap
         else:
             ypos=self.pmos_inst[index].by()-2*self.gap
         pos1 = vector(pin.lx()-2*self.m1_pitch, pin.by())
         pos2 = vector(pos1.x, ypos)
         self.add_path("m2", [pos1, pos2])
    
    def cnt_pmos_vstrap(self):
            """ connect vvdd and vdd ports of sleep-transistors to vertical straps """ 
            
            xpos=self.pmos_inst[0].lx()+0.5*self.pg.width
            
            pos1=self.pmos_inst[self.size-1].get_pins("vvdd")[0].uc()
            pos4=self.pmos_inst[self.size-1].get_pins("vvdd")[1].uc()
            pos2=vector(pos1.x, self.pmos_inst[self.size-1].uy()+2*self.m1_pitch)
            pos3=vector(pos4.x, self.pmos_inst[self.size-1].uy()+2*self.m1_pitch)
            pos3b=vector(pos4.x, self.pmos_inst[self.size-1].uy()+self.m1_pitch)
            pos5=(self.v_rail_pos[3],pos3b.y)
            self.add_path("m2", [pos1, pos2, pos3, pos4])
            self.add_wire(self.m1_stack, [pos4, pos3b, pos5], widen_short_wires=False)
            self.add_via_center(self.m1_stack, pos5, size=[self.num_via, 1])

            pos1=self.pmos_inst[0].get_pins("vdd")[0].uc()
            pos4=self.pmos_inst[0].get_pins("vdd")[1].uc()
            pos2=vector(pos1.x, self.pmos_inst[0].by()-2*self.m1_pitch)
            pos3=vector(pos4.x, self.pmos_inst[0].by()-2*self.m1_pitch)
            pos3b=vector(pos1.x, self.pmos_inst[0].by()-self.m1_pitch)
            pos5=(self.v_rail_pos[2],pos3b.y)
            self.add_path("m2", [pos1, pos2, pos3, pos4])
            self.add_wire(self.m1_stack, [pos1, pos3b, pos5], widen_short_wires=False)
            self.add_via_center(self.m1_stack, pos5, size=[self.num_via, 1])

    def cnt_pmos_hstrap(self, vvddshift, vddshift):
        """ connect vvdd and vdd ports of sleep-transistors to horizantal straps """ 

        yoff = self.pmos_inst[0].get_pin("sleep").lc().y
        for j in range(self.size):
            for pin in self.pmos_inst[j].get_pins("vdd"):
                self.add_path("m2", [(pin.uc().x, yoff), (pin.uc().x, yoff-vvddshift)])
                self.add_via_center(self.m2_stack, (pin.uc().x, yoff-vvddshift), size=[1, self.num_via])
            for pin in self.pmos_inst[j].get_pins("vvdd"):
                self.add_path("m2", [(pin.uc().x, yoff), (pin.uc().x, yoff+vddshift)])
                self.add_via_center(self.m2_stack, (pin.uc().x, yoff+vddshift), size=[1, self.num_via])

    def cnt_pmos_vsleep(self, mod):
            """ connect output of vertical sleep buffer to sleep port of sleep-transistors """ 

            pin = self.pmos_inst[0].get_pin("sleep")
            pos1=self.dc_inst.get_pin("out")
            pos2=vector(pos1.rx()+self.m1_pitch, pos1.lc().y)
            pos3=vector(pos2.x, mod.get_pin("sleep").lc().y)
            self.add_wire(self.m1_stack, [pos1.lc(), pos2, pos3], widen_short_wires=False)
            shift = 0.5*(self.m3_width-self.m1_width)
            for i in range(self.size):
                pin=self.pmos_inst[i].get_pin("sleep")
                if i%2:
                    self.add_via_center(self.m2_stack, (pos2.x, pin.lc().y+shift), rotate=90)
                    self.add_path("m3", [pin.lc(), (pos2.x, pin.lc().y+shift)])
                else:
                    self.add_via_center(self.m2_stack, (pos2.x, pin.lc().y-shift), rotate=90)
                    self.add_path("m3", [pin.lc(), (pos2.x, pin.lc().y-shift)])
    
    def cnt_buffer_vsleep(self, mod):
            """ connect output of vertical sleep buffer to sleep port of sleep-transistors """ 

            pin = mod.get_pin("sleep")
            pos1=vector(pin.lx()-self.m1_pitch, pin.lc().y)
            pos2=vector(pos1.x, self.dc_inst.get_pin("in").lc().y)
            pos3=self.dc_inst.get_pin("in").lc()
            self.add_wire(self.m1_stack, [pin.lc(), pos1, pos2, pos3], widen_short_wires=False)
    
    def cnt_pmos_hsleep(self, index):
        """ connect output of horizontal sleep buffer to sleep port of sleep-transistors """ 

        pin = self.pmos_inst[index].get_pin("sleep")
        pin2=self.dc_inst.get_pin("out").lc()
        if index==0:
            xpos=self.pmos_inst[index].lx()-2*self.m1_space
            xpos2=self.pmos_inst[index].lx()
        else:
            xpos=self.pmos_inst[index].rx()+2*self.m1_space
            xpos2=self.pmos_inst[index].rx()
        mid_pos=(xpos, pin2.y)
        mid_pos2=(xpos, pin.lc().y)
        mid_pos3=(xpos2, pin.lc().y)
        self.add_path("m1", [pin2, mid_pos, mid_pos2, mid_pos3])
    
    def cnt_corner_sleep(self, index, direction):
        """ connect output of sleep buffer to sleep port of sleep-transistors in perpendicular direction""" 
        
        pin = self.pmos_inst[index].get_pin("sleep")
        pos4=vector(self.dc_inst.get_pin("in").lx(), self.dc_inst.get_pin("in").lc().y)
        
        if direction=="h":
            pos1=vector(self.pmos_inst[index].rx(), pin.lc().y)
        else:
            pos1=vector(pin.lx(), pin.lc().y)
            pos2=vector(pos1.x-self.m1_pitch, pos1.y)
        
        if direction=="h":
            pos2=vector(pos4.x-self.m1_pitch, pos1.y)
            gnd_pin1=vector(self.pmos_inst[index].lx(), self.gnd_ypos)
            gnd_pin2=vector(self.dc_inst.get_pin("gnd").lx()-2*self.m1_pitch, gnd_pin1.y)
            gnd_pin3=vector(gnd_pin2.x, self.dc_inst.get_pin("gnd").uy())
        else:
            gnd_pin1=vector(self.gnd_xpos, self.pmos_inst[index].uy())
            gnd_pin2=vector(gnd_pin1.x, self.dc_inst.get_pin("gnd").lc().y)
            gnd_pin3=self.dc_inst.get_pin("gnd").lc()
        
        pos3=vector(pos2.x, pos4.y)
        self.add_wire(self.m1_stack, [pos1, pos2, pos3, pos4], widen_short_wires=False)
        self.add_wire(self.m1_stack, [gnd_pin1, gnd_pin2, gnd_pin3], widen_short_wires=False)

    def cnt_sleep_pin2(self):
        """ connect sleep pin of sram to sleep pin of pmos tx """
        
        pin1=self.pmos_inst[self.size-1].get_pin("sleep")
        pin2=self.dc_inst.get_pin("in")

        pos1=vector(self.v_rail_pos[2] - self.strap_w - self.m1_pitch, pin1.lc().y)
        pos2=vector(pos1.x, pin2.lc().y)
        self.add_wire(self.m1_stack, [(self.pmos_inst[self.size-1].rx(), pin1.lc().y), pos1, pos2, pin2.lc()], widen_short_wires=False)

        pin1=self.pmos_inst[self.size-1]
        pin2=self.dc_inst.get_pin("gnd")

        pos1=vector(self.v_rail_pos[2] - self.strap_w - 2*self.m1_pitch, pin1.by())
        pos2=vector(pos1.x, pin2.lc().y)
        self.add_wire(self.m1_stack, [(pin1.rx(), pin1.by()), pos1, pos2, pin2.lc()], widen_short_wires=False)

    
    def cnt_sleep_pin(self):
        """ connect sleep pin of sram to sleep pin of first sleep-buffer """
        
        pin1=self.dc_inst.get_pin("in")
        pin2=self.sram_inst.get_pin("sleep")

        if pin2.layer[:2] == "m1":
            if pin1.by() > pin2.by():
                pos1=vector(0.5*self.vstrap_w-self.m1_pitch, pin1.lc().y)
                pos2=vector(pos1.x, pin2.lc().y)
                self.add_wire(self.m1_stack, [pin1.lc(), pos1, pos2, pin2.lc()], widen_short_wires=False)
            else:
                pos1=vector(pin2.rx()+self.m1_pitch, pin2.lc().y)
                pos2=vector(pos1.x, self.sram_inst.get_pin("vdd").uy())
                pos3=vector(pin1.lx()-self.m1_pitch, pos2.y)
                pos4=vector(pos3.x, pin1.lc().y)
                self.add_wire(self.m1_stack, [pin2.lc(), pos1, pos2, pos3, pos4, pin1.lc()], widen_short_wires=False)
        
        else:
            pos1=vector(pin2.uc().x, self.sram_inst.get_pin("gnd").uy())
            pos2=vector(0.5*self.vstrap_w-self.m1_pitch, pos1.y)
            pos3=vector(pos2.x, pin1.lc().y)
            self.add_wire(self.m1_stack, [pin2.uc(), pos1, pos2, pos3, pin1.lc()], widen_short_wires=False)

        pin1=self.dc_inst.get_pin("gnd")
        pin2=self.sram_inst.get_pin("gnd")
        pos0=pin1.lc()
        pos1=vector(0.5*self.vstrap_w+self.m1_pitch, pin1.lc().y)
        pos2=vector(pos1.x, pin2.lc().y)
        self.add_wire(self.m1_stack, [pos0, pos1, pos2], widen_short_wires=False)
        self.add_via_center(self.m2_stack, pos2, size=[1, self.num_via])
        
    def create_pmos_group(self, orien, pos, num):
        """ create a group of sleep-transistors """ 
        
        self.pmos_inst={}
        if orien == "V":
            pos+=vector(4*self.m1_pitch+contact.m1m2.width, 0)
            off=pos
            for i in range(self.size):
                if i%2:
                    mirror="MX"
                    off=pos+vector(0, (i+1)*self.pg.height)
                else: 
                    mirror="R0"
                self.pmos_inst[i] = self.add_inst(name="pmos{}".format(i+num*self.size), mod=self.pg, offset=off, mirror=mirror)
                self.connect_inst(["sleep{}".format(num), "vvdd", "vdd"])
            
        
        if orien == "H":
            for i in range(self.size): 
                self.pmos_inst[i] = self.add_inst(name="pmos{}".format(i+num*self.size), mod=self.pg, offset=pos+vector(i*self.pg.width, 0))
                self.connect_inst(["sleep{}".format(num), "vvdd", "vdd"])

    def sp_write(self, sp_name):
        """ Write the entire spice of the object to the file """
        sp = open(sp_name, 'w')

        sp.write("**************************************************\n")
        sp.write("* AMC generated memory\n")
        sp.write("* Number of Words: {}\n".format(self.total_bits//self.word_size))
        sp.write("* Word Size: {}bit\n".format(self.word_size))
        sp.write("* Number of Banks: {}\n".format(self.num_inbanks*self.num_outbanks))
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
        print("\n SRAM SPICE: Writing to {0}".format(spname))
        self.sp_write(spname)
        print_time("SRAM Spice writing", datetime.datetime.now(), start_time)

        # Save the extracted spice file if requested
        if OPTS.use_pex:
            start_time = datetime.datetime.now()
            sp_file = OPTS.output_path + "temp_pex.sp"
            calibre.run_pex(self.name, gdsname, spname, output=sp_file)
            print_time("SRAM Extraction", datetime.datetime.now(), start_time)
        else:
            # Use generated spice file for characterization
            sp_file = spname
        
        # Write the layout
        start_time = datetime.datetime.now()
        gdsname = OPTS.output_path + self.name + ".gds"
        print("\n SRAM GDS: Writing to {0}".format(gdsname))
        self.gds_write(gdsname)
        print_time("SRAM GDS writing", datetime.datetime.now(), start_time)

        # Create a LEF physical model
        start_time = datetime.datetime.now()
        lefname = OPTS.output_path + self.name + ".lef"
        print("\n SRAM LEF: Writing to {0}".format(lefname))
        self.lef_write(lefname)
        print_time("SRAM LEF writing", datetime.datetime.now(), start_time)

        # Write a verilog model
        start_time = datetime.datetime.now()
        vname = OPTS.output_path + self.name + ".v"
        print("\n SRAM Verilog: Writing to {0}".format(vname))
        self.verilog_write(vname)
        print_time("SRAM Verilog writing", datetime.datetime.now(), start_time)
        
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
