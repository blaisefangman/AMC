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
import utils
from vector import vector
from tech import GDS,layer
import endcells
from bitcell import bitcell
class endcells_frame(design.design):
    """
    This module implements the end-cells for SRAM array used in the design. End-cells are 
    foundry cells, so the layout and netlist should be available in the technology library.
    """
    def __init__(self, cols, rows, name="endcells_frame"):

        design.design.__init__(self, name)
        debug.info(1, "Creating {0} for a {1} x {2}array".format(name, rows, cols))

        self.col_size = cols
        self.row_size = rows

        self.strap_logic = endcells.endcell1()
        self.add_mod(self.strap_logic)
        
        self.strap_logic_endcell_flip = endcells.endcell2()
        self.add_mod(self.strap_logic_endcell_flip)

        self.wl_endcell = endcells.endcell3()
        self.add_mod(self.wl_endcell)
        
        self.wl_endcell_prog = endcells.endcell4()
        self.add_mod(self.wl_endcell_prog)

        self.corner_endcell_flip = endcells.endcell5()
        self.add_mod(self.corner_endcell_flip)        

        self.bl_endcell = endcells.endcell6()
        self.add_mod(self.bl_endcell)
        
        self.cell = bitcell()
        self.add_mod(self.cell)
                
        self.add_pins()

        self.create_bottom_strap()
        self.create_top_strap()
        self.create_left_strap()
        self.create_right_strap()
        self.add_layout_pins()
        self.offset_all_coordinates()
        
        
        self.bot_width=self.strap_logic_endcell_flip.height
        self.top_width=self.bl_endcell.height
        self.left_width=self.wl_endcell.width
        self.right_width= self.wl_endcell.width
        
        self.width = self.left_width + self.right_width + self.col_size*self.bl_endcell.width
        self.height=self.bot_width + self.top_width + self.row_size*self.wl_endcell.height
    
    
    def add_pins(self):
        """ Add pins for bitcell_array, order of the pins is important """
        
        for col in range(self.col_size):
            self.add_pin("bl[{0}]".format(col))
            self.add_pin("br[{0}]".format(col))
        for row in range(self.row_size):
            self.add_pin("wl[{0}]".format(row))
        self.add_pin_list(["vdd", "gnd", "vdds", "gnds"])
                 
        

    def create_bottom_strap(self):
        
        self.strap_inst ={}
        for i in range(self.col_size):
            if i%2:
                mirror = "R0"
                rotate=180
                xoff=(i+1)*self.strap_logic.width
            else:
                mirror="MX"
                rotate=0
                xoff=i*self.strap_logic.width
            
            self.strap_inst[i]=self.add_inst(name="strap_logic{}".format(i), 
                                             mod=self.strap_logic, 
                                             offset=(xoff,0), 
                                             mirror=mirror,
                                             rotate=rotate)
            # gnds vdds nmost bl pmost
            self.connect_inst(["gnds", "vdds", "gnd", "bl[{0}]".format(i), "vdd"])
        
        
        self.add_inst(name="strap_logic_endcell_right", 
                      mod=self.strap_logic_endcell_flip, 
                      offset=(self.strap_logic.width*self.col_size, 0), 
                      mirror="MX")
        #gnds vdds bld
        #self.connect_inst(["gnds", "vdds", "bld_right0"])
        self.connect_inst(["in_r", "vdds", "gnds", "gnd"])
       
        self.strap_inst = self.add_inst(name="strap_logic_endcell_flip_left", 
                      mod=self.strap_logic_endcell_flip, 
                      offset=(0, 0),
                      mirror="R0",
                      rotate=180)
        #in vdds gnds nmost
        self.connect_inst(["in_l", "vdds", "gnds", "gnd"])
        

    def create_top_strap(self):
    
        self.bl_inst={}
        for i in range(self.col_size):
            if i%2:
                mirror = "MY"
                xoff=(i+1)*self.bl_endcell.width
            else:
                mirror="R0"
                xoff=i*self.bl_endcell.width
            
            self.bl_inst[i]=self.add_inst(name="bl_endcell{}".format(i), 
                                          mod=self.bl_endcell, 
                                          offset=(xoff, self.wl_endcell.height*self.row_size), 
                                          mirror=mirror)
            #gnds vdds nmost bl pmost
            self.connect_inst(["gnds", "vdds", "gnd", "bl[{0}]".format(i), "vdd"])
        
        
        self.add_inst(name="corner_endcell_right", 
                      mod=self.corner_endcell_flip, 
                      offset=(self.strap_logic.width*self.col_size, self.wl_endcell.height*self.row_size), 
                      mirror="R0")
        
        #gnds vdds bld
        #self.connect_inst(["gnds", "vdds", "bld_right{}".format(self.row_size/2)])
        self.connect_inst(["pd_right", "vdds", "gnds", "gnd"])
       
        self.corner_inst = self.add_inst(name="corner_endcell_flip_left", 
                      mod=self.corner_endcell_flip, 
                      offset=(0, self.wl_endcell.height*self.row_size),
                      mirror="MX",
                      rotate=180)
        #in vdds gnds nmost
        self.connect_inst(["pd_left", "vdds", "gnds", "gnd"])
        

    def create_left_strap(self):
        
        self.wl_cell_left={}
        for i in range(self.row_size-1):
            if i%2:
                mirror = "MX"
                yoff=i*self.wl_endcell.height
            else:
                mirror="R0"
                yoff=(i+1)*self.wl_endcell.height
            self.wl_cell_left[i]=self.add_inst(name="wl_endcell_left{}".format(i), 
                                               mod=self.wl_endcell, 
                                               offset=(0, yoff), 
                                               mirror=mirror,
                                               rotate=180)
            #wl bld gnd gnds
            self.connect_inst(["wl[{0}]".format(i), "bld_left{}".format(i//2), "gnd", "gnds"])

        self.add_inst(name="wl_endcell_prog_left", 
                      mod=self.wl_endcell_prog, 
                      offset=(0, self.wl_endcell.height*(self.row_size-1)), 
                      mirror="MX",
                      rotate=180)
        #wl pd bld gnd gnds
        self.connect_inst(["wl[{0}]".format(self.row_size-1), "pd_left", "bld_left{}".format((self.row_size-1)//2), "gnd", "gnds"])


    def create_right_strap(self):

        self.wl_cell_right={}
        for i in range(self.row_size):
            if i%2:
                mirror = "R0"
                yoff=i*self.wl_endcell.height
            else:
                mirror="MX"
                yoff=(i+1)*self.wl_endcell.height
            self.wl_cell_right[i]=self.add_inst(name="wl_endcell_right{}".format(i), 
                                                 mod=self.wl_endcell, 
                                                 offset=(self.bl_endcell.width*self.col_size, yoff), 
                                                 mirror=mirror)
            #wl bld gnd gnds
            self.connect_inst(["wl[{0}]".format(i), "bld_right{}".format(i//2), "gnd", "gnds"])
            
    def add_layout_pins(self):

        for i in ["vdds", "gnds"]:
            for pin in [self.corner_inst.get_pin(i), self.strap_inst.get_pin(i)]:
                self.add_layout_pin(text=i,
                                    layer= pin.layer,
                                    offset=pin.ll(),
                                    width= pin.width(),
                                    height= pin.height())
