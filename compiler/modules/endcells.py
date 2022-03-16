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
from tech import GDS,layer

""" This module implements the end-cells for SRAM array used in the design. End-cells are 
    foundry cells, so the layout and netlist should be available in the technology library. """


class endcell1(design.design):
    pin_names = ["gnds", "vdds", "nmost", "bl", "pmost"]
    (width,height) = utils.get_libcell_size("sp28_0152_SW_strap_logic", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "sp28_0152_SW_strap_logic", GDS["unit"])
    def __init__(self):
        design.design.__init__(self, "sp28_0152_SW_strap_logic")
        debug.info(2, "Create sp28_0152_SW_strap_logic")
        self.width = endcell1.width
        self.height = endcell1.height
        self.pin_map = endcell1.pin_map

class endcell2(design.design):
    pin_names = ["in", "vdds", "gnds", "nmost"]
    (width,height) = utils.get_libcell_size("sp28_0152_SW_strap_logic_endcell_flip", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "sp28_0152_SW_strap_logic_endcell_flip", GDS["unit"])
    def __init__(self):
        design.design.__init__(self, "sp28_0152_SW_strap_logic_endcell_flip")
        debug.info(2, "Create sp28_0152_SW_strap_logic_endcell_flip")
        self.width = endcell2.width
        self.height = endcell2.height
        self.pin_map = endcell2.pin_map

class endcell3(design.design):
    pin_names = ["wl", "bld", "gnd"]
    (width,height) = utils.get_libcell_size("sp28_0152_SW_wl_endcell", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "sp28_0152_SW_wl_endcell", GDS["unit"])
    def __init__(self):
        design.design.__init__(self, "sp28_0152_SW_wl_endcell")
        debug.info(2, "Create sp28_0152_SW_wl_endcell")
        self.width = endcell3.width
        self.height = endcell3.height
        self.pin_map = endcell3.pin_map

class endcell4(design.design):
    pin_names = ["wl", "pd", "bld", "gnd"]
    (width,height) = utils.get_libcell_size("sp28_0152_SW_wl_endcell_prog", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "sp28_0152_SW_wl_endcell_prog", GDS["unit"])
    def __init__(self):
        design.design.__init__(self, "sp28_0152_SW_wl_endcell_prog")
        debug.info(2, "Create sp28_0152_SW_wl_endcell_prog")
        self.width = endcell4.width
        self.height = endcell4.height
        self.pin_map = endcell4.pin_map


class endcell5(design.design):
    pin_names = ["in", "vdds", "gnds", "nmost"]
    (width,height) = utils.get_libcell_size("sp28_0152_SW_corner_endcell_flip", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "sp28_0152_SW_corner_endcell_flip", GDS["unit"])
    def __init__(self):
        design.design.__init__(self, "sp28_0152_SW_corner_endcell_flip")
        debug.info(2, "Create sp28_0152_SW_corner_endcell_flip")
        self.width = endcell5.width
        self.height = endcell5.height
        self.pin_map = endcell5.pin_map

class endcell6(design.design):
    pin_names = ["gnds", "vdds", "nmost", "bl", "pmost"]
    (width,height) = utils.get_libcell_size("sp28_0152_SW_bl_endcell", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "sp28_0152_SW_bl_endcell", GDS["unit"])
    def __init__(self):
        design.design.__init__(self, "sp28_0152_SW_bl_endcell")
        debug.info(2, "Create sp28_0152_SW_bl_endcell")
        self.width = endcell6.width
        self.height = endcell6.height
        self.pin_map = endcell6.pin_map
