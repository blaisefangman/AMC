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


import design
import debug
from vector import vector
from split import split

class split_array(design.design):
    """ Array of dynamically generated split cells for multi bank SRAM. """

    def __init__(self, word_size, words_per_row, name=""):
        
        if name=="":
            name = "split_array_{0}_{1}".format(word_size, words_per_row)
        design.design.__init__(self, name )
        debug.info(1, "Creating {0}".format(name))

        self.split = split()
        self.add_mod(self.split)

        self.word_size = word_size
        self.words_per_row = words_per_row
        self.name = name
        self.row_size = self.word_size * self.words_per_row

        self.height = self.split.height
        self.width = self.split.width * self.word_size * self.words_per_row

        self.add_pins()
        self.create_layout()

    def add_pins(self):
        """ Add pins for split_array, order of the pins is important """
        
        for i in range(0,self.row_size,self.words_per_row):
            self.add_pin("D[{0}]".format(i // self.words_per_row))
            self.add_pin("Q[{0}]".format(i // self.words_per_row))
        self.add_pin_list(["en1_S", "en2_S", "reset", "S", "vdd", "gnd"])

    def create_layout(self):
        """ Create modules for instantiation and then route"""

        self.add_split()
        self.connect_rails()

    def add_split(self):
        """ Add split cells """
            
        D_pin = self.split.get_pin("D")
        Q_pin = self.split.get_pin("Q")
        self.split_inst= {}
        
        for i in range(0,self.row_size,self.words_per_row):
            name = "split{0}".format(i)
            split_position = vector(self.split.width * i, 0)

            if (self.words_per_row==1 and i%2):
                mirror = "MY"
                split_position = vector(i * self.split.width + self.split.width,0)
            else:
                mirror = "R0"
            
            self.split_inst[i] = self.add_inst(name=name, mod=self.split, offset=split_position, mirror=mirror)
            self.connect_inst(["D[{0}]".format(i // self.words_per_row), 
                               "Q[{0}]".format(i // self.words_per_row), 
                               "en1_S", "en2_S", "reset", "S", "vdd", "gnd"])
            
            D_offset = self.split_inst[i].get_pin("D").ll()
            Q_offset = vector(self.split_inst[i].get_pin("Q").lx() , self.height-self.m2_width)

            self.add_layout_pin(text="D[{0}]".format(i // self.words_per_row), 
                                layer=D_pin.layer, 
                                offset=D_offset, 
                                width=D_pin.width(), 
                                height=self.m2_width)
            self.add_layout_pin(text="Q[{0}]".format(i // self.words_per_row), 
                                layer=Q_pin.layer, 
                                offset=Q_offset, 
                                width=Q_pin.width(), 
                                height=self.m2_width)

    def connect_rails(self):
        """ Add vdd, gnd, en1_s, en2_s, reset and select rails across entire array"""
        
        #vdd 
        vdd_pin = self.split.get_pin("vdd")
        self.add_rect(layer="metal1", 
                      offset=vdd_pin.ll().scale(0,1), 
                      width=self.width, 
                      height=self.m1_width)
        self.add_layout_pin(text="vdd", 
                            layer=vdd_pin.layer, 
                            offset=vdd_pin.ll().scale(0,1), 
                            width=vdd_pin.height(), 
                            height=vdd_pin.height())

        #gnd 
        gnd_pin = self.split.get_pin("gnd")
        self.add_rect(layer="metal1", 
                      offset=gnd_pin.ll().scale(0,1), 
                      width=self.width, 
                      height=self.m1_width)
        self.add_layout_pin(text="gnd", 
                            layer=gnd_pin.layer, 
                            offset=gnd_pin.ll().scale(0,1), 
                            width=gnd_pin.height(), 
                            height=gnd_pin.height())

        #en1_S
        en1_pin = self.split.get_pin("en1_S")
        self.add_rect(layer="metal1", 
                      offset=en1_pin.ll().scale(0,1), 
                      width=self.width, 
                      height=self.m1_width)
        self.add_layout_pin(text="en1_S", 
                            layer=en1_pin.layer, 
                            offset=en1_pin.ll().scale(0,1), 
                            width=self.m1_width, 
                            height=self.m1_width)

        #en2_S
        en2_pin = self.split.get_pin("en2_S")
        self.add_rect(layer="metal1", 
                      offset=en2_pin.ll().scale(0,1), 
                      width=self.width, 
                      height=self.m1_width)
        self.add_layout_pin(text="en2_S", 
                            layer=en2_pin.layer, 
                            offset=en2_pin.ll().scale(0,1), 
                            width=self.m1_width, 
                            height=self.m1_width)
        
        # reset
        reset_pin = self.split.get_pin("reset")
        self.add_rect(layer="metal1", 
                      offset=reset_pin.ll().scale(0,1), 
                      width=self.width, 
                      height=self.m1_width)
        self.add_layout_pin(text="reset", 
                            layer=reset_pin.layer, 
                            offset=reset_pin.ll().scale(0,1), 
                            width=self.m1_width, 
                            height=self.m1_width)

        # S
        sel_pin = self.split.get_pin("S")
        self.add_rect(layer="metal1", 
                      offset=sel_pin.ll().scale(0,1), 
                      width=self.width, 
                      height=self.m1_width)
        self.add_layout_pin(text="S", 
                            layer=sel_pin.layer, 
                            offset=sel_pin.ll().scale(0,1), 
                            width=self.m1_width, 
                            height=self.m1_width)

