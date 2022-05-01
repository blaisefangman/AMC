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


import design
import debug
import contact
import math
from vector import vector
from xor2 import xor2
from nand2 import nand2
from nand3 import nand3
from pinv import pinv
from nor_tree import nor_tree
from flipflop import flipflop
from pull_up_pull_down import pull_up_pull_down
from ptx import ptx
from utils import ceil

class comparator(design.design):
    """ Dynamically generated comparator to comapre data-in and data-out in BIST """

    def __init__(self, size, name="comparator"):
        """ Constructor """

        design.design.__init__(self, name)
        debug.info(1, "Creating {}".format(name))

        self.size = size
        
        self.create_layout()
        self.offset_all_coordinates()

    def create_layout(self):
        """ Create layout, route between modules and adding pins """
        
        self.add_pins()
        self.create_modules()
        self.setup_layout_constants()
        self.add_modules()
        self.connect_modules()
        self.add_layout_pins()
        self.width= max(self.xor_inst[self.size-1].rx(), self.latch_inst.rx())+\
                    4*self.m1_pitch+self.m2_width
        self.height= self.nor_tree_inst.uy()+6*self.m1_pitch+self.m2_width

    def add_pins(self):
        """ Adds pins for lfsr module """
        
        for i in range(self.size):
            self.add_pin("din{0}".format(i))
        for i in range(self.size):
            self.add_pin("dout{0}".format(i))
        self.add_pin_list(["error", "lfsr_done", "reset", "r", "clk", "vdd", "gnd"])

    def create_modules(self):
        """ construct all the required modules """
        
        self.ff = flipflop()
        self.add_mod(self.ff)
        
        self.xor2 = xor2()
        self.add_mod(self.xor2)

        self.nand2 = nand2()
        self.add_mod(self.nand2)

        self.nand3 = nand3()
        self.add_mod(self.nand3)
        
        self.inv = pinv()
        self.add_mod(self.inv)

        self.inv5 = pinv(size=5)
        self.add_mod(self.inv5)
        
        self.nor_tree=nor_tree(size=self.size+1, name="comparator_nor_tree")
        self.add_mod(self.nor_tree)
        
        self.latch=pull_up_pull_down(num_nmos=2, num_pmos=1, 
                                     nmos_size=2, pmos_size=2, 
                                     vdd_pins=[], gnd_pins=[], name="comp_latch")
        self.add_mod(self.latch)
        
    def setup_layout_constants(self):
        """ Setup layout constants, spaces, etc """

        self.pin_off = 2*self.m1_pitch
        
        #This is a gap between neighbor cell to avoid well/implant DRC violation
        self.gap1= max(self.implant_space, self.well_space, self.m1_pitch)+contact.m1m2.width
        self.gap2= self.gap1+2*self.m1_pitch
        self.con_yshift =  0.5*abs(contact.poly.second_layer_height-contact.poly.first_layer_height)

    def add_modules(self):
        """ Adds all modules in the following order"""

        self.add_flipflop()
        self.add_clk_gate()
        self.add_xor()
        self.add_nor_tree()
        self.add_latch()

    def connect_modules(self):
        """ Route modules """

        self.connect_FF_to_XOR()
        self.connect_clk_to_FF()
        self.connect_XOR_to_nor_tree()
        self.connect_vdd_gnd()
    
    def add_flipflop(self):
        """ Place the flipflops """
        
        self.ff_inst={}
        x_shisht = self.inv.width+self.inv5.width+self.nand3.width+\
                   4*self.m1_pitch-self.ff.width
        for i in range(self.size):
            off=(x_shisht+i*(self.ff.width+self.gap2),0)
            self.ff_inst[i]= self.add_inst(name="flipflop{0}".format(i),
                                           mod=self.ff,
                                           offset=off)
            self.connect_inst(["din{0}".format(i), "out{0}".format(i), "bx{0}".format(i), "clkin", "reset", "vdd", "vdd", "gnd"])

    def add_clk_gate(self):
        """ Place the inv and nand3 for clk gateing with reset and lfsr_done signals """
        
        self.reset_inv_inst= self.add_inst(name="inv_reset",
                                           mod=self.inv,
                                           offset=(0,self.ff_inst[0].uy()+self.gap1))
        self.connect_inst(["reset", "reset_b", "vdd", "gnd"])

        off=self.reset_inv_inst.lr()+vector(4*self.m1_pitch,0)
        self.reset_nand_inst= self.add_inst(name="nand3_reset",
                                            mod=self.nand3,
                                            offset=off)
        self.connect_inst(["reset_b", "lfsr_done", "clk", "q", "vdd", "gnd"])
        
        self.clk_inv_inst= self.add_inst(name="inv_clk",
                                         mod=self.inv5,
                                         offset=self.reset_nand_inst.lr())
        self.connect_inst(["q", "clkin", "vdd", "gnd"])
        
        pos2=self.reset_nand_inst.get_pin("A").lc()
        pos1=self.reset_inv_inst.get_pin("Z").lc()
        mid_pos=vector(pos1.x+self.m1_pitch, pos1.y)
        self.add_path("m1", [pos1, mid_pos, pos2])
            
    def add_xor(self):
        """ Place the xor gates above flipflops """
        
        self.xor_inst={}
        for i in range(self.size):
            xoff = max(self.ff_inst[0].rx() , self.clk_inv_inst.rx()) + self.gap2
            yoff = self.ff_inst[0].uy()+self.gap1
            off = (xoff + i*(self.ff.width+self.gap2),yoff)
            self.xor_inst[i]= self.add_inst(name="xor{0}".format(i),
                                            mod=self.xor2,
                                            offset=off)
            self.connect_inst(["out{0}".format(i), "dout{0}".format(i), "z{0}".format(i), "vdd", "gnd"])
    
    def add_nor_tree(self):
        """ Place the nor-tree above xor gates """
        
        xoff=self.ff_inst[1].rx()+self.gap2
        yoff=self.xor_inst[0].uy()+(self.size+2)*self.m1_pitch
        self.nor_tree_inst= self.add_inst(name="nor_tree",
                                           mod=self.nor_tree,
                                           offset=(xoff,yoff))
        temp=[]
        for i in range(self.size):
            temp.append("z{0}".format(i))
        
        temp.extend(["err_bar", "vdd", "gnd"])
        self.connect_inst(temp)
    
        off=(self.nor_tree_inst.rx(),self.nor_tree_inst.by()+self.m1_pitch)
        self.inv_err= self.add_inst(name="inv_err", mod=self.inv, offset=off)
        self.connect_inst(["err_bar", "err1", "vdd", "gnd"])

        self.nand_err= self.add_inst(name="nand_err", mod=self.nand3,
                                     offset=self.inv_err.lr()+vector(self.gap2, 0))
        self.connect_inst(["reset_b", "err1", "r", "err_b", "vdd", "gnd"])


        self.inv_inst= self.add_inst(name="inv", mod=self.inv, offset=self.nand_err.lr())
        self.connect_inst(["err_b", "err", "vdd", "gnd"])
        
        pos1=self.inv_err.get_pin("Z").lc()
        pos2=(self.inv_err.rx()+self.m1_width, pos1.y)
        pos3=self.nand_err.get_pin("B").lc()
        self.add_path("m1", [pos1,pos2, pos3])

        pos1=self.nand_err.get_pin("A").lc()
        pos2=vector(pos1.x-self.m1_pitch, pos1.y)
        pos3=vector(pos2.x, self.nand_err.uy()+2*self.m1_pitch)
        pos5=self.reset_inv_inst.get_pin("Z").ll()-vector(0.5*self.m2_width, 0)
        pos4=vector(pos5.x, pos3.y)
        self.add_wire(self.m1_stack, [pos1, pos2, pos3, pos4, pos5], widen_short_wires=False)

    def add_latch(self):
        """ Add the final latch to capture error signal """
        
        shift = 0.5*abs(contact.m1m2.width - contact.poly.width)
        off=self.inv_inst.lr()+vector(self.gap2, -0.5*contact.m1m2.width)
        self.latch_inst= self.add_inst(name="latch", mod=self.latch, offset=off)
        self.connect_inst(["err", "err_bar", "net1", "r", "error", "err", "r", "error", "vdd", "gnd"])
        
        pos1 = self.latch_inst.get_pin("Gp0").lc()-vector(self.m1_pitch+contact.poly.height, 0)
        self.add_path("poly", [self.latch_inst.get_pin("Gn0").lc(), pos1])
        pos3=vector(pos1.x+contact.poly.first_layer_height, self.latch_inst.get_pin("Gp0").by()-contact.poly.width)
        self.add_contact(self.poly_stack, pos3+vector(self.con_yshift, 0), rotate=90)
        self.add_contact(self.m1_stack, pos3+vector(0, shift), rotate=90)
        
        width=ceil(self.minarea_m1/contact.m1m2.width)
        self.add_rect(layer="m1", offset=pos3-vector(width, -shift), width=width, height=contact.m1m2.width)        
        
        pos2 = self.latch_inst.get_pin("Gn1").lc()+vector(2*self.m1_pitch, 0)
        pos2a=vector(self.latch_inst.lx()+self.implant_enclose_poly, pos2.y+0.5*self.poly_width)
        pos2b=vector(self.latch_inst.get_pin("Dp0").rx()+2*contact.poly.height, pos2a.y)
        pos2c=vector(pos2b.x, pos2.y)
        self.add_path("poly", [pos2a, pos2b, pos2c, pos2])
        
        pos4=vector(pos2.x, self.latch_inst.get_pin("Gn1").ul().y)
        self.add_contact(self.poly_stack, pos4+(self.con_yshift, -shift), rotate=90)
        self.add_contact(self.m1_stack, pos4, rotate=90)
        self.add_rect(layer="m1", offset=pos4, width=width, height=contact.m1m2.width)
        
        self.add_rect_center(layer="m1", offset=self.latch_inst.get_pin("Dn0").cc(), width=width, height=contact.m1m2.width)        
        
        self.add_path("m1",[self.latch_inst.get_pin("Dp0").uc() , self.latch_inst.get_pin("Dn1").lc()])
        pos11=self.inv_inst.get_pin("Z").lc()
        pos12=vector(pos11.x+self.m1_pitch, pos11.y)
        pos14=self.latch_inst.get_pin("Dp0").lc()
        pos13=vector(pos12.x, pos14.y)
        self.add_path("m1",[pos11,pos12, pos13, pos14])
        
        #connect output of inverter to input of latch (Gn1)
        pos5=self.nor_tree_inst.get_pin("out").lc()+vector(0, contact.m1m2.width-self.m1_width)
        pos6=vector(self.nor_tree_inst.rx(), self.inv_err.uy()+3*self.m1_pitch)
        pos7=vector(pos2.x, pos6.y)
        pos8=pos2+vector(-0.5*self.m2_width, 0.5*self.m2_width)
        self.add_wire(self.m1_stack, [pos8, pos7, pos6, pos5], widen_short_wires=False)
        
        #Connect r to input of latch (Gp0)
        pos9=vector(0, self.nand_err.uy()+4*self.m1_pitch)
        pos10=vector(pos3.x, pos9.y)
        self.add_wire(self.m1_stack, [pos9,pos10, pos3], widen_short_wires=False)
    
    def connect_clk_to_FF(self):
        """ Connect output of clk_inv to clk pin of FF """
        pos1=self.clk_inv_inst.get_pin("Z").ll()-vector(0.5*self.m2_width, self.v1_via_shift)
        pos3=vector(pos1.x, self.clk_inv_inst.uy()+5*self.m1_pitch)
        pos4=vector(self.reset_inv_inst.lx()-self.m1_pitch,pos3.y)
        pos6=self.ff_inst[self.size-1].get_pin("clk").lc()
        pos5=vector(pos4.x, pos6.y)
        self.add_wire(self.m1_stack, [pos1, pos3, pos4, pos5, pos6], widen_short_wires=False)

    def connect_FF_to_XOR(self):
        """ Connect FF output to input A of XOR """
        
        for i in range(self.size):
            pos1=self.ff_inst[i].get_pin("out").lc()
            pos2=vector(self.ff_inst[i].rx()+self.m1_pitch, pos1.y)
            pos4=self.xor_inst[i].get_pin("A").lc()
            pos3=(pos2.x, pos4.y)
            self.add_wire(self.m1_stack,[pos1, pos2, pos3, pos4], widen_short_wires=False)
        
    def connect_XOR_to_nor_tree(self):
        """ Connect XOR output to inputs of nor_tree """
        
        for i in range(self.size):
            y_off=self.xor_inst[0].uy()+(i+1)*self.m1_pitch
            self.add_path("m1",[(self.xor_inst[0].lx(), y_off), 
                                    (self.xor_inst[self.size-1].rx(), y_off)])
            pos1=self.xor_inst[i].get_pin("Z")
            pos2=vector(pos1.rx(), y_off)
            self.add_path("m2",[pos1.lr(),pos2])
            self.add_via_center(self.m1_stack, (pos1.rx(), pos1.lc().y))
            self.add_via_center(self.m1_stack, pos2)
            
            pos3=self.nor_tree_inst.get_pin("in{0}".format(i)).uc()
            pos4=vector(pos3.x, y_off)
            self.add_path("m2", [pos3, pos4])
            self.add_via_center(self.m1_stack, pos4+vector(0, self.v1_via_shift))

    def connect_vdd_gnd(self):
        """ Connect vdd and gnd of all modules to vdd and gnd pins """
        
        modules=[self.inv_inst, self.ff_inst[self.size-1], 
                 self.xor_inst[self.size-1], self.reset_nand_inst]
        pins=["vdd", "gnd"]
        
        for mod in modules:
            for i in range(2):
                pos1=mod.get_pin(pins[i]).lc()
                pos2=vector(self.reset_inv_inst.lx()-(4+i)*self.m1_pitch, pos1.y)
                self.add_path("m1", [pos1, pos2])
                self.add_via_center(self.m1_stack, (pos2.x+0.5*self.m2_width, pos2.y), rotate=90)
            
        #connect vdd and gnd of latch to self.inv_inst
        xoff=self.inv_inst.rx()-0.5*self.m1_width
        for pin in ["vdd", "gnd"]:
            self.add_path("m1", [(xoff, self.inv_inst.get_pin(pin).lc().y),self.latch_inst.get_pin(pin).lc()])
        
        #connect rst1 of FF to vdd 
        for i in range(self.size):
            rst1_pin = self.ff_inst[i].get_pin("rst1")
            vdd_pin = self.ff_inst[i].get_pin("vdd")
            xoff = self.ff_inst[i].lx()+2*self.m2_space
            self.add_path("m2", [(xoff, rst1_pin.lc().y), (xoff, vdd_pin.lc().y)])
            self.add_via_center(self.m1_stack, (xoff, rst1_pin.lc().y), rotate=90)
            self.add_via_center(self.m1_stack, (xoff, vdd_pin.lc().y), rotate=90)

    def add_layout_pins(self):
        """ Adds all input, ouput and power pins"""
        
        #reset pin
        xpos=-5*self.m1_pitch
        rst_pin = self.reset_inv_inst.get_pin("A")
        self.add_path("m1", [(xpos, rst_pin.lc().y), rst_pin.lc()])
        self.add_layout_pin(text="reset",
                            layer="m1",
                            offset=(xpos, rst_pin.by()),
                            width=self.m1_width,
                            height=self.m1_width)
        
        #connect rst0 of FF to reset 
        for i in range(self.size):
            rst0_pin = self.ff_inst[i].get_pin("rst0")
            yoff = self.ff_inst[i].by()-self.m1_pitch
            xoff = self.ff_inst[i].lx()+2*self.m1_pitch
            self.add_path("m2", [(xoff, rst0_pin.lc().y), (xoff, yoff)])
            self.add_via_center(self.m1_stack, (xoff, rst0_pin.lc().y), rotate=90)
            self.add_via_center(self.m1_stack, (xoff, yoff), rotate=90)
        
        pos1=vector(self.ff_inst[self.size-1].rx(), yoff)
        pos2=vector(-2*self.m1_pitch, pos1.y)
        pos3=vector(pos2.x, rst_pin.lc().y)
        pos4=vector(xpos, pos3.y)
        self.add_wire(self.m1_stack, [pos1, pos2, pos3, pos4], widen_short_wires=False)


        #lfsr_done & clk pin
        pins=["B", "C"]
        labels=["lfsr_done", "clk"]
        for i in range(2):
            pin = self.reset_nand_inst.get_pin(pins[i])
            x_off = pin.lc().x-(i+1)*self.m1_pitch
            y_off = max(self.reset_nand_inst.uy(), self.xor_inst[0].uy())+(i+1)*self.m1_pitch
            self.add_wire(self.m1_stack, [(xpos, y_off), (x_off, y_off), 
                                          (x_off, pin.lc().y), pin.lc()], widen_short_wires=False)
            self.add_layout_pin(text=labels[i],
                                layer="m1",
                                offset=(xpos, y_off-0.5*self.m1_width),
                                width=self.m1_width,
                                height=self.m1_width)

        #r pin
        pos1=self.nand_err.get_pin("C").lc()
        pos2=vector(pos1.x-2*self.m1_pitch, pos1.y)
        pos3=vector(pos2.x, self.nand_err.uy()+4*self.m1_pitch)
        pos4=vector(xpos, pos3.y)
        self.add_wire(self.m1_stack, [pos1, pos2, pos3, pos4], widen_short_wires=False)
        self.add_layout_pin(text="r",
                            layer="m1",
                            offset=pos4-vector(0, 0.5*self.m1_width),
                            width=self.m1_width,
                            height=self.m1_width)

        #din inputs to FFs
        for i in range(self.size):
            pos1=self.ff_inst[i].get_pin("in").lc()
            pin_off=vector(pos1.x-self.m1_pitch, self.ff_inst[i].by()-self.m1_pitch)
            self.add_wire(self.m1_stack, [pin_off,pos1], widen_short_wires=False)
            self.add_layout_pin(text="din{0}".format(i),
                                layer="m2",
                                offset=(pin_off.x-0.5*self.m2_width, pin_off.y),
                                width=self.m2_width,
                                height=self.m2_width)

        #dout inputs to XORs
        for i in range(self.size):
            pin=self.xor_inst[i].get_pin("B")
            pin_off=vector(pin.lc().x-self.m1_pitch, self.nor_tree_inst.uy()+6*self.m1_pitch)
            self.add_path("m3", [pin_off, pin.lc()])
            self.add_rect_center(layer="m2", 
                                 offset=(pin.lx()+0.5*self.m2_width,pin.uc().y),
                                 width=self.m2_width,
                                 height=self.minarea_m2/self.m2_width)
            self.add_via(self.m1_stack, (pin.lc()-vector(0, 0.5*self.m2_width)))
            self.add_via(self.m2_stack, (pin.lc()-vector(0, 0.5*self.m3_width)))
            self.add_layout_pin(text="dout{0}".format(i),
                                layer="m3",
                                offset=(pin_off.x-0.5*self.m3_width, pin_off.y-self.m3_width),
                                width=self.m3_width,
                                height=self.m3_width)
        #output pin
        pin=self.latch_inst.get_pin("Sp0")
        x_off = max(self.xor_inst[self.size-1].rx(), self.latch_inst.rx())+self.m1_pitch
        self.add_path("m1", [pin.lc(), (x_off, pin.lc().y)])
        self.add_layout_pin(text="error",
                            layer="m1",
                            offset=(x_off-self.m1_width, pin.by()),
                            width=self.m1_width,
                            height=self.m1_width)

        #vdd & gnd pins
        pins=["vdd", "gnd"]
        height=self.nor_tree_inst.uy()-self.ff_inst[0].by()+self.m1_pitch
        for i in range(2):
            off=(self.reset_inv_inst.lx()-(i+4)*self.m1_pitch,-self.m1_pitch)
            self.add_rect(layer="m2",
                          offset=off,
                          width=self.m2_width,
                          height=height)
            self.add_layout_pin(text=pins[i],
                               layer="m2",
                               offset=off,
                               width=self.m2_width,
                               height=self.m2_width)
        
