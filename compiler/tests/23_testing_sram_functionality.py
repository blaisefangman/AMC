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


""" Run a regresion test on SRAM functionality. """

import unittest
from testutils import header,AMC_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug
import importlib as imp

class sram_func_test(AMC_test):

    def runTest(self):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))
        OPTS.check_lvsdrc = False

        # This is a hack to reload the characterizer __init__ with the spice version
        import async_characterizer
        imp.reload(async_characterizer)
        from async_characterizer import async_functional_test
        import async_sram
        import tech

        debug.info(1, "Testing timing for sample 1bit, 16words SRAM with 1 bank")
        s = async_sram.sram(word_size=8, words_per_row=1, num_rows=64, num_subanks=2, 
                      branch_factors=(1,2), bank_orientations=("H", "H"), mask=False, 
                      power_gate=False, name="sram")
                      
        tempspice = OPTS.openram_temp + "sram.sp"
        s.sp_write(tempspice)
        
        corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])
        size = (s.addr_size, s.w_size)
        
        
        #at least 4 simulation is needed to calculate delays for each operation
        T = async_functional_test.functional_test(size, corner, name=s.name, 
                                            w_per_row = s.w_per_row, num_rows = s.num_rows, 
                                            mask=s.mask, power_gate=s.power_gate, 
                                            load=tech.spice["input_cap"], 
                                            slew=tech.spice["rise_time"])

        globals.end_openram()
        
# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
