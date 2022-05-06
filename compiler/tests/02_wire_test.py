############################################################################
#
# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
############################################################################


"Run a regresion test on a basic wire. "

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class wire_test(openram_test):

    def runTest(self):
        config_file = "{0}/tests/configs/async/config_20_{1}".format(os.getenv("AMC_HOME"), OPTS.tech_name)
        globals.init_openram(config_file)

        import wire
        import tech
        import design
        

        min_space = 2 * (tech.drc["minwidth_m2"] + tech.drc["minwidth_m1"])
        layer_stack = ("m1", "via1", "m2")
        position_list = [[0, 0],
                         [0, 3 * min_space],
                         [1 * min_space, 3 * min_space],
                         [4 * min_space, 3 * min_space],
                         [4 * min_space, 0],
                         [7 * min_space, 0],
                         [7 * min_space, 4 * min_space],
                         [-1 * min_space, 4 * min_space],
                         [-1 * min_space, 0]]
        w = design.design("wire_test1")
        wire.wire(w, layer_stack, position_list)
        self.local_drc_check(w)


        min_space = 2 * (tech.drc["minwidth_m2"] + tech.drc["minwidth_m1"])
        layer_stack = ("m2", "via1", "m1")
        position_list = [[0, 0],
                         [0, 3 * min_space],
                         [1 * min_space, 3 * min_space],
                         [4 * min_space, 3 * min_space],
                         [4 * min_space, 0],
                         [7 * min_space, 0],
                         [7 * min_space, 4 * min_space],
                         [-1 * min_space, 4 * min_space],
                         [-1 * min_space, 0]]
        w = design.design("wire_test2")
        wire.wire(w, layer_stack, position_list)
        self.local_drc_check(w)

        min_space = 2 * (tech.drc["minwidth_m2"] + tech.drc["minwidth_m3"])
        layer_stack = ("m2", "via2", "m3")
        position_list = [[0, 0],
                         [0, 3 * min_space],
                         [1 * min_space, 3 * min_space],
                         [4 * min_space, 3 * min_space],
                         [4 * min_space, 0],
                         [7 * min_space, 0],
                         [7 * min_space, 4 * min_space],
                         [-1 * min_space, 4 * min_space],
                         [-1 * min_space, 0]]
        position_list.reverse()
        w = design.design("wire_test3")
        wire.wire(w, layer_stack, position_list)
        self.local_drc_check(w)

        min_space = 2 * (tech.drc["minwidth_m2"] + tech.drc["minwidth_m3"])
        layer_stack = ("m3", "via2", "m2")
        position_list = [[0, 0],
                         [0, 3 * min_space],
                         [1 * min_space, 3 * min_space],
                         [4 * min_space, 3 * min_space],
                         [4 * min_space, 0],
                         [7 * min_space, 0],
                         [7 * min_space, 4 * min_space],
                         [-1 * min_space, 4 * min_space],
                         [-1 * min_space, 0]]
        position_list.reverse()
        w = design.design("wire_test4")
        wire.wire(w, layer_stack, position_list)
        self.local_drc_check(w)

        globals.end_openram()
        

# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
