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


""" Run a regresion test on a comparator module in bist. """

import unittest
from testutils import header, openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class bist_comparator_test(openram_test):

    def runTest(self):
        config_file = "{0}/tests/configs/async/config_20_{1}".format(os.getenv("AMC_HOME"), OPTS.tech_name)
        globals.init_openram(config_file)
        
        import comparator

        #minimum size is 2 bit
        debug.info(1, "Testing 2 input comparator")
        a = comparator.comparator(size=2, name="comparator_2")
        self.local_check(a)

        debug.info(1, "Testing 3 input comparator")
        a = comparator.comparator(size=3, name="comparator_3")
        self.local_check(a)

        debug.info(1, "Testing 8 input comparator")
        a = comparator.comparator(size=8, name="comparator_8")
        self.local_check(a)

        debug.info(1, "Testing 32 input comparator")
        a = comparator.comparator(size=32, name="comparator_32")
        self.local_check(a)
        
        globals.end_openram()
        
# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
