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


""" Generate the LIB file for an SRAM. """

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug
import importlib as imp

class lib_test(openram_test):

    def runTest(self):
        config_file = "{0}/tests/configs/async/config_20_{1}".format(os.getenv("AMC_HOME"), OPTS.tech_name)
        globals.init_openram(config_file)

        # This is a hack to reload the characterizer __init__ with the spice version
        import async_characterizer
        imp.reload(async_characterizer)
        from async_characterizer import async_lib
        import async_sram
        import tech

        #**** Setup synopsys' Finesim and VCS before running this test ***#
        debug.info(1, "Testing timing for sample 1bit, 16words SRAM with 1 bank")
        s = async_sram.sram(word_size=4, words_per_row=1, num_rows=32, num_subanks=1, 
                      branch_factors=(1,1), bank_orientations=("H", "H"), mask=False, power_gate=False, name="sram")
                      
        tempspice = OPTS.openram_temp + "sram.sp"
        s.sp_write(tempspice)
        
        
        async_lib.lib(OPTS.openram_temp, s)

        globals.end_openram()
        
# TEST NOT IMPLEMENTED
# instantiate a copdsay of the class to actually run the test
#if __name__ == "__main__":
    #(OPTS, args) = globals.parse_args()
    #del sys.argv[1:]
    #header(__file__, OPTS.tech_name)
    #unittest.main()
