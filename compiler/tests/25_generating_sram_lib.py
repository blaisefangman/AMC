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
from testutils import header,AMC_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class lib_test(AMC_test):

    def runTest(self):
        globals.init_AMC("config_20_{0}".format(OPTS.tech_name))

        # This is a hack to reload the characterizer __init__ with the spice version
        import characterizer
        reload(characterizer)
        from characterizer import lib
        import sram
        import tech

        #**** Setup synopsys' Finesim and VCS before running this test ***#
        debug.info(1, "Testing timing for sample 1bit, 16words SRAM with 1 bank")
        s = sram.sram(word_size=4, words_per_row=1, num_rows=32, num_subanks=1, 
                      branch_factors=(1,1), bank_orientations=("H", "H"), name="sram")
                      
        tempspice = OPTS.AMC_temp + "sram.sp"
        s.sp_write(tempspice)
        
        
        lib.lib(OPTS.AMC_temp, s)

        globals.end_AMC()
        
# instantiate a copdsay of the class to actually run the test
#if __name__ == "__main__":
    #(OPTS, args) = globals.parse_args()
    #del sys.argv[1:]
    #header(__file__, OPTS.tech_name)
    #unittest.main()
