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


""" Run a regresion test on various size banks. """

import unittest
from testutils import header,AMC_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class bank_test(AMC_test):

    def runTest(self):
        globals.init_AMC("config_20_{0}".format(OPTS.tech_name), is_unit_test=False)
        
        global calibre
        import calibre
        OPTS.check_lvsdrc = False

        import bank

        debug.info(1, "Single Bank Test")
        """ range of acceptable value: 
        
        word_size is any number greater than 1
        word_per_row in [1, 2, 4] 
        num_rows in [32, 64, 128, 256]
        num_subanks in [1, 2, 4, 8]
        two_level_bank [False, True] : if True split and merge cells will be added
        
        """
        a = bank.bank(word_size=16, words_per_row=1, num_rows=32, 
                      num_subanks=2, two_level_bank=True, mask=False, 
                      power_gate=True, name="bank")

        self.local_check(a)

        OPTS.check_lvsdrc = True
        # return it back to it's normal state
        globals.end_AMC()
        
        
# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)

    unittest.main()
