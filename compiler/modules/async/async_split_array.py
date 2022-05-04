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
from vector import vector
from async_split import split

class split_array(design.design):
    """ Array of dynamically generated split cells for multi bank SRAM. """

    def __init__(self, word_size, words_per_row, mask, name=""):
        
        if name=="":
            name = "split_array_{0}_{1}".format(word_size, words_per_row)
        design.design.__init__(self, name )
        debug.info(1, "Creating {0}".format(name))

        self.word_size = word_size
        self.words_per_row = words_per_row
        self.name = name
        self.mask = mask
        self.row_size = self.word_size * self.words_per_row
        
        self.split = split()
        self.add_mod(self.split)
        
        if self.mask:
            from async_split import split2
            
            self.split2 = split2()
            self.add_mod(self.split2)

        self.height = self.split.height
        if self.mask:
            self.height = self.split2.height
        self.width = self.split.width * self.word_size * self.words_per_row

        self.add_pins()
        self.create_layout()

    def add_pins(self):
        """ Add pins for split_array, order of the pins is important """
        
        for i in range(0,self.row_size,self.words_per_row):
            self.add_pin("D[{0}]".format(i//self.words_per_row))
            self.add_pin("Q[{0}]".format(i//self.words_per_row))
        if self.mask:
            for i in range(0,self.row_size,self.words_per_row):
                self.add_pin("bm_in[{0}]".format(i//self.words_per_row))
                self.add_pin("bm_out[{0}]".format(i//self.words_per_row))

        self.add_pin_list(["en1_S", "en2_S", "reset", "S", "vdd", "gnd"])

    def create_layout(self):
        """ Create modules for instantiation and then route"""

        self.add_split()
        self.connect_rails()

    def add_split(self):
        """ Add split cells """
            
        D_pin = self.split.get_pin("D")
        Q_pin = self.split.get_pin("Q")
        
        if self.mask:
            bm_in_pin = self.split2.get_pin("bm_in")
            bm_out_pin = self.split2.get_pin("bm_out")
            mod = self.split2
        else: 
            mod= self.split

        self.split_inst= {}
        
        for i in range(0,self.row_size,self.words_per_row):
            name = "split{0}".format(i)
            split_position = vector(self.split.width * i, 0)

            if (self.words_per_row==1 and i%2):
                mirror = "MY"
                split_position = vector(i * self.split.width + self.split.width,0)
            else:
                mirror = "R0"
            
            self.split_inst[i] = self.add_inst(name=name, mod=mod, offset=split_position, mirror=mirror)

            temp = ["D[{0}]".format(i//self.words_per_row),"Q[{0}]".format(i//self.words_per_row)]
            if self.mask:
                temp.extend(["bm_in[{0}]".format(i//self.words_per_row),"bm_out[{0}]".format(i//self.words_per_row)])
            
            temp.extend(["en1_S", "en2_S", "reset", "S", "vdd", "gnd"])
            self.connect_inst(temp)
            
            D_offset = self.split_inst[i].get_pin("D")
            Q_offset = vector(self.split_inst[i].get_pin("Q").lx() , self.height-self.m2_width)

            self.add_layout_pin(text="D[{0}]".format(i//self.words_per_row), 
                                layer=D_offset.layer, 
                                offset=D_offset.ll(), 
                                width=self.m3_width, 
                                height=self.m2_width)
            self.add_layout_pin(text="Q[{0}]".format(i//self.words_per_row), 
                                layer=Q_pin.layer, 
                                offset=Q_offset, 
                                width=Q_pin.width(), 
                                height=self.m2_width)
            if self.mask:
                bm_in_offset = self.split_inst[i].get_pin("bm_in").ll()
                bm_out_offset = vector(self.split_inst[i].get_pin("bm_out").lx() , self.split_inst[i].get_pin("bm_out").uy()-self.m2_width)
                self.add_layout_pin(text="bm_in[{0}]".format(i//self.words_per_row), 
                                layer=bm_in_pin.layer, 
                                offset=bm_in_offset, 
                                width=bm_in_pin.width(), 
                                height=self.m2_width)
                self.add_layout_pin(text="bm_out[{0}]".format(i//self.words_per_row), 
                                layer=bm_out_pin.layer, 
                                offset=bm_out_offset, 
                                width=bm_out_pin.width(), 
                                height=self.m2_width)

    def connect_rails(self):
        """ Add vdd, gnd, en1_s, en2_s, reset and select rails across entire array"""
        
        pin_list = ["vdd", "gnd", "S", "en1_S", "en2_S", "reset"]
        for i in pin_list:
            pin=self.split_inst[0].get_pin(i)
            self.add_rect(layer="m1", 
                          offset=pin.ll().scale(0,1),
                          width=self.width, 
                          height=self.m1_width)
            self.add_layout_pin(text=i, 
                                layer=pin.layer, 
                                offset=pin.ll().scale(0,1),
                                width=pin.width(), 
                                height=pin.height())
