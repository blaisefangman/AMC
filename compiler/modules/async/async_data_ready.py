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


""" This module implements the data_ready cells used in the completion detion in read mode. 
    The layout and netlist of each cell should be available in the technology library. """

class data_ready(design.design):

    pin_names = ["bl", "br", "sen", "dr", "vdd", "gnd"]
    (width,height) = utils.get_libcell_size("data_ready", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "data_ready", GDS["unit"])
    

    def __init__(self):
        design.design.__init__(self, "data_ready")
        debug.info(2, "Create data_ready")

        self.width = data_ready.width
        self.height = data_ready.height
        self.pin_map = data_ready.pin_map
