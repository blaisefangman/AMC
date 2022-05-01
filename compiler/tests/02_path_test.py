############################################################################
#
# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
############################################################################


"Run a regresion test on a basic path. "

import unittest
from testutils import header,AMC_test
import sys, os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class path_test(AMC_test):

    def runTest(self):
        globals.init_AMC("config_20_{0}".format(OPTS.tech_name))
        global calibre
        import calibre
        OPTS.check_lvsdrc = False

        import wire_path
        import tech
        import design

        min_space = 2 * tech.drc["minwidth_m1"]
        layer = ("m1")
        # checks if we can retrace a path
        position_list = [[0,0],
                         [0, 3 * min_space ],
                         [4 * min_space, 3 * min_space ],
                         [4 * min_space, 3 * min_space ],
                         [0, 3 * min_space ],
                         [0, 6 * min_space ]]
        w = design.design("path_test0")
        wire_path.wire_path(w,layer, position_list)
        self.local_drc_check(w)


        min_space = 2 * tech.drc["minwidth_m1"]
        layer = ("m1")
        old_position_list = [[0, 0],
                             [0, 3 * min_space],
                             [1 * min_space, 3 * min_space],
                             [4 * min_space, 3 * min_space],
                             [4 * min_space, 0],
                             [7 * min_space, 0],
                             [7 * min_space, 4 * min_space],
                             [-1 * min_space, 4 * min_space],
                             [-1 * min_space, 0]]
        position_list  = [[x+min_space, y+min_space] for x,y in old_position_list]
        w = design.design("path_test1")
        wire_path.wire_path(w,layer, position_list)
        self.local_drc_check(w)

        min_space = 2 * tech.drc["minwidth_m2"]
        layer = ("m2")
        old_position_list = [[0, 0],
                             [0, 3 * min_space],
                             [1 * min_space, 3 * min_space],
                             [4 * min_space, 3 * min_space],
                             [4 * min_space, 0],
                             [7 * min_space, 0],
                             [7 * min_space, 4 * min_space],
                             [-1 * min_space, 4 * min_space],
                             [-1 * min_space, 0]]
        position_list  = [[x-min_space, y-min_space] for x,y in old_position_list]
        w = design.design("path_test2")
        wire_path.wire_path(w, layer, position_list)
        self.local_drc_check(w)

        min_space = 2 * tech.drc["minwidth_m3"]
        layer = ("m3")
        position_list = [[0, 0],
                         [0, 3 * min_space],
                         [1 * min_space, 3 * min_space],
                         [4 * min_space, 3 * min_space],
                         [4 * min_space, 0],
                         [7 * min_space, 0],
                         [7 * min_space, 4 * min_space],
                         [-1 * min_space, 4 * min_space],
                         [-1 * min_space, 0]]
        
        # run on the reverse list
        position_list.reverse()
        w = design.design("path_test3")
        wire_path.wire_path(w, layer, position_list)
        self.local_drc_check(w)

        # return it back to it's normal state
        OPTS.check_lvsdrc = True
        globals.end_AMC()
        

# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
