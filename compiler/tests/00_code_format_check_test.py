############################################################################
#
# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
############################################################################


import unittest
from testutils import header, AMC_test
import sys, os, re
sys.path.append(os.path.join(sys.path[0],".."))
import globals
import debug

class code_format_test(AMC_test):
    "Run a test to check for tabs instead of spaces in the all source files."

    def runTest(self):
        source_code_dir = os.environ["AMC_HOME"]
        source_codes = setup_files(source_code_dir)
        errors = 0

        for code in source_codes:
            if re.search("gdsMill", code):
                continue
            errors += check_file_format_tab(code)

        for code in source_codes:
            if re.search("gdsMill", code):
                continue
            if re.search("options.py$", code):
                continue
            if re.search("debug.py$", code):
                continue
            if re.search("testutils.py$", code):
                continue
            if re.search("grid.py$", code):
                continue
            if re.search("globals.py$", code):
                continue
            if re.search("AMC.py$", code):
                continue
            if re.search("functional_test.py$", code):
                continue
            errors += check_print_output(code)

        # fails if there are any tabs in any files
        self.assertEqual(errors, 0)

def setup_files(path):
    files = []
    for (dir, _, current_files) in os.walk(path):
        for f in current_files:
            files.append(os.path.join(dir, f))
    nametest = re.compile("\.py$", re.IGNORECASE)
    select_files = filter(nametest.search, files)
    return select_files


def check_file_format_tab(file_name):
    """Check if any files contain tabs and return the number of tabs."""
    
    f = open(file_name, "r+b")
    key_positions = []
    for num, line in enumerate(f, 1):
        if b'\t' in line:
            key_positions.append(num)
    if len(key_positions) > 0:
        debug.info(0, '\nFound ' + str(len(key_positions)) + ' tabs in ' +
                   str(file_name) + ' (line ' + str(key_positions[0]) + ')')
    f.close()
    return len(key_positions)


def check_print_output(file_name):
    """Check if any files (except debug.py) call the _print_ function. We should
       use the debug output with verbosity instead!"""
    
    file = open(file_name, "r+b")
    line = file.read()
    # skip comments with a hash
    line = re.sub(r'#.*', '', line)
    # skip doc string comments
    line=re.sub(r'\"\"\"[^\"]*\"\"\"', '', line, flags=re.S|re.M)
    count = len(re.findall(r"\s*print\s+", line))
    count2 = len(re.findall(r"\s*.print\s+", line))
    if (count-count2) > 0:
        debug.info(0, "\nFound " + str(count-count2) + " _print_ calls " + str(file_name))
    file.close()
    return(count)


# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
