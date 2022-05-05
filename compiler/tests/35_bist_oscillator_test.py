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


""" Run a regresion test on a stopable ring-oscillator module in bist. """

import unittest
from testutils import header, AMC_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class bist_oscillator_test(AMC_test):

    def runTest(self):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))
        
        global calibre
        import calibre
        OPTS.check_lvsdrc = False

        import oscillator

        if OPTS.tech_name == "scn3me_subm":
            debug.info(1, "Testing oscillator")
            #delay value in nsec
            a = oscillator.oscillator(delay=5, name="oscillator1")
            self.local_check(a)
            
            #delay value in nsec
            a = oscillator.oscillator(delay=10, name="oscillator2")
            self.local_check(a)
        
        if OPTS.tech_name == "tsmc65nm":
            debug.info(1, "Testing oscillator")
            #delay value in nsec
            a = oscillator.oscillator(delay=0.81, name="oscillator1")
            self.local_check(a)

            #delay value in nsec
            a = oscillator.oscillator(delay=0.35, name="oscillator2")
            self.local_check(a)

        if OPTS.tech_name == "cmos28fdsoi":
            debug.info(1, "Testing oscillator")
            #delay value in nsec
            a = oscillator.oscillator(delay=0.22, name="oscillator1")
            self.local_check(a)

            #delay value in nsec
            a = oscillator.oscillator(delay=0.17, name="oscillator2")
            self.local_check(a)

        # return it back to it's normal state
        OPTS.check_lvsdrc = True
        globals.end_openram()
        
# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
