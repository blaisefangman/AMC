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


""" Run a regresion test on bist. """

import unittest
from testutils import header, openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class bist_test(openram_test):

    def runTest(self):
        config_file = "{0}/tests/configs/async/config_20_{1}".format(os.getenv("AMC_HOME"), OPTS.tech_name)
        globals.init_openram(config_file)
        
        import bist

        #with async_bist=False ring-oscillator won't be added to design
        
        #minimum size is 3 bit 
        if OPTS.tech_name == "tsmc65nm":
            debug.info(1, "Testing 3bit bist")
            a = bist.bist(addr_size=12, data_size=16, delay = 1, async_bist=True, name="bist")
            self.local_check(a)

            a = bist.bist(addr_size=7, data_size=8, delay = 0.2, async_bist=True, name="bist2")
            self.local_check(a)
        
        if OPTS.tech_name == "cmos28fdsoi":
            debug.info(1, "Testing 3bit bist")
            a = bist.bist(addr_size=6, data_size=2, delay = 1, async_bist=True, name="bist")
            self.local_check(a)
            
            a = bist.bist(addr_size=9, data_size=8, delay = 0.3, async_bist=True, name="bist2")
            self.local_check(a)

        
        if OPTS.tech_name == "scn3me_subm":
            debug.info(1, "Testing 12bit bist")
            a = bist.bist(addr_size=4, data_size=4, delay = 10, async_bist=True, name="bist")
            self.local_check(a)

            debug.info(1, "Testing 12bit bist")
            a = bist.bist(addr_size=10, data_size=8, delay = 2, async_bist=True, name="bist2")
            self.local_check(a)
        
        globals.end_openram()
        
# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
