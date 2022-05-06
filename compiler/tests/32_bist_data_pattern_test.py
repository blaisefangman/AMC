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


""" Run a regresion test on a data pattern generation module in bist. """

import unittest
from testutils import header, openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class bist_data_pattern_test(openram_test):

    def runTest(self):
        config_file = "{0}/tests/configs/async/config_20_{1}".format(os.getenv("AMC_HOME"), OPTS.tech_name)
        globals.init_openram(config_file)
        
        import data_pattern

        #minimum size is 3 bit
        debug.info(1, "Testing 4bit input-data pattern")
        a = data_pattern.data_pattern(size=4, name="data_pattern_4")
        self.local_check(a)

        debug.info(1, "Testing 12bit input-data pattern")
        a = data_pattern.data_pattern(size=12, name="data_pattern_12")
        self.local_check(a)
        
        globals.end_openram()
        
# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
