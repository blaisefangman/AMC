############################################################################
#
# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
############################################################################


"Run a regresion test on a basic parameterized transistors. "

import unittest
from testutils import header, openram_test
import sys, os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class ptx_test(openram_test):

    def runTest(self):
        config_file = "{0}/tests/configs/async/config_20_{1}".format(os.getenv("AMC_HOME"), OPTS.tech_name)
        globals.init_openram(config_file)
        
        import async_ptx
        import tech

        debug.info(2, "Checking single finger NMOS")
        fet1 = async_ptx.ptx(width= tech.drc["minwidth_tx"],
                       mults=1, tx_type="nmos", connect_active=False, connect_poly=False)
        #self.local_drc_check(fet1)

        debug.info(2, "Checking single finger PMOS")
        fet2 = async_ptx.ptx(width= 2*tech.drc["minwidth_tx"],
                       mults=1, tx_type="pmos", connect_active=False, connect_poly=False)
        #self.local_drc_check(fet2)

        debug.info(2, "Checking three fingers NMOS")
        fet3 = async_ptx.ptx(width=3*tech.drc["minwidth_tx"],
                       mults=3, tx_type="nmos", connect_active=False, connect_poly=False)
        #self.local_drc_check(fet3)

        debug.info(2, "Checking foure fingers PMOS")
        fet4 = async_ptx.ptx(width=2*tech.drc["minwidth_tx"],
                       mults=4, tx_type="pmos", connect_active=True, connect_poly=True)
        #self.local_drc_check(fet4)

        debug.info(2, "Checking three fingers NMOS")
        fet5 = async_ptx.ptx(width=3*tech.drc["minwidth_tx"],
                       mults=4, tx_type="nmos", connect_active=True, connect_poly=False)
        #self.local_drc_check(fet5)

        debug.info(2, "Checking foure fingers PMOS")
        fet6 = async_ptx.ptx(width=2*tech.drc["minwidth_tx"],
                       mults=3, tx_type="pmos", connect_active=False, connect_poly=True)
        #self.local_drc_check(fet6)

        globals.end_openram()

# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
