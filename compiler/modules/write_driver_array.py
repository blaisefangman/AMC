############################################################################
#
# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
############################################################################


import design
import debug
from vector import vector
from write_driver import write_driver

class write_driver_array(design.design):
    """ Array of dynamically generated write drivers to drive input data to the bitlines.  """

    def __init__(self, word_size, words_per_row, mask, name = "write_driver_array"):
        design.design.__init__(self, name)
        debug.info(1, "Creating {0}".format(name))

        self.write_driver = write_driver()
        self.add_mod(self.write_driver)

        self.word_size = word_size
        self.words_per_row = words_per_row
        self.name = name
        self.mask = mask
        self.row_size = self.word_size * self.words_per_row

        self.width = self.word_size * self.words_per_row * self.write_driver.width
        self.height = self.write_driver.height
        
        self.add_pins()
        self.create_layout()

    def add_pins(self):
        """ Add pins for write_driver_array, order of the pins is important """
        
        for i in range(0, self.row_size, self.words_per_row):
            self.add_pin("data[{0}]".format(i//self.words_per_row))
            self.add_pin("bm[{0}]".format(i//self.words_per_row))
            self.add_pin_list(["bl[{0}]".format(i), "br[{0}]".format(i)])
        self.add_pin_list(["en", "pchg", "vdd","gnd"])

    def create_layout(self):
        """ Create modules for instantiation and then route"""

        self.add_write_driver()
        self.connect_rails()

    def add_write_driver(self):
        """ Add write driver cells"""
        
        bl_pin = self.write_driver.get_pin("bl")            
        br_pin = self.write_driver.get_pin("br")
        din_pin = self.write_driver.get_pin("din")
        bm_pin = self.write_driver.get_pin("bm")

        self.wd_inst={}

        for i in range(0, self.row_size, self.words_per_row):
            name = "write_driver{}".format(i)
            wd_position = vector(i * self.write_driver.width,0)
            
            if (self.words_per_row==1 and i%2):
                mirror = "MY"
                wd_position = vector(i * self.write_driver.width + self.write_driver.width,0)
            else:
                mirror = "R0"
            
            self.wd_inst[i] = self.add_inst(name=name, mod=self.write_driver, offset=wd_position, mirror = mirror)
            
            temp=["data[{0}]".format(i//self.words_per_row), "bm[{0}]".format(i//self.words_per_row)]
            temp.extend(["bl[{0}]".format(i),"br[{0}]".format(i), "en", "pchg", "vdd", "gnd"])
            
            self.connect_inst(temp)
            
            bl_offset = vector(self.wd_inst[i].get_pin("bl").lx() , self.height-self.m2_width)
            br_offset = vector(self.wd_inst[i].get_pin("br").lx() , self.height-self.m2_width)
            din_offset = self.wd_inst[i].get_pin("din").ll()
            bm_offset = self.wd_inst[i].get_pin("bm").ll()

            self.add_layout_pin(text="data[{0}]".format(i//self.words_per_row),
                                layer=din_pin.layer, 
                                offset=din_offset, 
                                width=din_pin.width(), 
                                height=self.m2_width)
            self.add_layout_pin(text="bm[{0}]".format(i//self.words_per_row),
                                layer=bm_pin.layer, 
                                offset=bm_offset, 
                                width=bm_pin.width(), 
                                height=self.m2_width)
                       
            self.add_layout_pin(text="bl[{0}]".format(i), 
                                layer=bl_pin.layer, 
                                offset=bl_offset, 
                                width=bl_pin.width(), 
                                height=self.m2_width)
            
            self.add_layout_pin(text="br[{0}]".format(i), 
                                layer=br_pin.layer, 
                                offset=br_offset, 
                                width=br_pin.width(), 
                                height=self.m2_width)

    def connect_rails(self):

        """ Add vdd, gnd, en and pchg rails across entire array """
        
        pin_list = ["vdd", "gnd", "en", "pchg"]
        for i in pin_list:
            pin=self.wd_inst[0].get_pin(i)
            self.add_rect(layer="m1", 
                          offset=pin.ll().scale(0,1),
                          width=self.width, 
                          height=self.m1_width)
            self.add_layout_pin(text=i, 
                                layer=pin.layer, 
                                offset=pin.ll().scale(0,1),
                                width=pin.width(), 
                                height=pin.height())
