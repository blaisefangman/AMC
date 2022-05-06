############################################################################
#
# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
############################################################################


""" Run a regresion test on a delay chain. """

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class delay_chain_test(openram_test):

    def runTest(self):
        config_file = "{0}/tests/configs/async/config_20_{1}".format(os.getenv("AMC_HOME"), OPTS.tech_name)
        globals.init_openram(config_file)
        
        import async_delay_chain

        debug.info(2, "Testing delay_chain, 10 stages")
        a = async_delay_chain.delay_chain(num_inv=17, num_stage=10, name="delay_chain1")
        self.local_check(a)
        
        debug.info(2, "Testing delay_chain, 3 stage")
        a = async_delay_chain.delay_chain(num_inv=11, num_stage=3, name="delay_chain2")
        self.local_check(a)

        debug.info(2, "Testing delay_chain, 1 stage")
        a = async_delay_chain.delay_chain(num_inv=6, num_stage=1, name="delay_chain3")
        self.local_check(a)

        globals.end_openram()
        
# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
