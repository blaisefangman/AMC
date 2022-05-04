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


""" Run regression tests on a parameterized pull_up_pull_down. This module doesn't
generate a multi_finger pull_up_pull_down network. """

import unittest
from testutils import header, AMC_test
import sys, os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class pull_up_pull_down_test(AMC_test):

    def runTest(self):
        globals.init_AMC("config_20_{0}".format(OPTS.tech_name))
        
        global calibre
        import calibre
        OPTS.check_lvsdrc = False

        import async_pull_up_pull_down
        
        debug.info(2, "Checking pull_up_pull_down gate")
        tx = async_pull_up_pull_down.pull_up_pull_down(num_nmos=2, num_pmos=1, 
                                                 nmos_size=2, pmos_size=1, 
                                                 vdd_pins=[], gnd_pins=[])
        self.local_check(tx)
        
        # return it back to it's normal state
        OPTS.check_lvsdrc = True
        globals.end_AMC()
        
# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
