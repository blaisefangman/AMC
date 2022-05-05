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


""" SRAM Compiler
The output files append the given suffixes to the output name:
a spice (.sp) file for circuit simulation
a GDS2 (.gds) file containing the layout
a Verilog (.v) file for Synthesis
a LEF (.lef) file for preliminary P&R
a Liberty (.lib) file for timing analysis/optimization
"""
#!/usr/bin/env python2

import sys, os
import datetime
import re
from globals import *

(OPTS, args) = parse_args()

# Check that we are left with a single configuration file as argument.
if len(args) != 1:
    print(USAGE)
    sys.exit(2)


# These depend on arguments, so don't load them until now.
import debug


init_openram(config_file=args[0], is_unit_test=False)

# Only print banner here so it's not in unit tests
print_banner()

# Output info about this run
report_status()

# Start importing design modules after we have the config file

# Characterizer is slow and deactivated by default
print("For .lib file: set the \"characterize = True\" in options.py, invoke Synopsys HSIM and VCS tools and rerun.\n")

# Keep track of running stats
start_time = datetime.datetime.now()
print_time("Start",start_time)

total_size=(OPTS.words_per_row * OPTS.num_rows * OPTS.num_subanks * OPTS.branch_factors[0] * OPTS.branch_factors[1])

if OPTS.power_gate:
    import async_power_gate_sram
    s = async_power_gate_sram.power_gate_sram(word_size=OPTS.word_size,
                                        words_per_row=OPTS.words_per_row, 
                                        num_rows=OPTS.num_rows, 
                                        num_subanks=OPTS.num_subanks, 
                                        branch_factors=OPTS.branch_factors, 
                                        bank_orientations=OPTS.bank_orientations,
                                        mask=OPTS.mask, 
                                        name="sram_{0}_{1}".format(OPTS.word_size, total_size))

    s.save_output()

else:
    import async_sram
    s = async_sram.sram(word_size=OPTS.word_size,
                  words_per_row=OPTS.words_per_row, 
                  num_rows=OPTS.num_rows, 
                  num_subanks=OPTS.num_subanks, 
                  branch_factors=OPTS.branch_factors, 
                  bank_orientations=OPTS.bank_orientations,
                  mask=OPTS.mask, 
                  power_gate=OPTS.power_gate,  
                  name="sram_{0}_{1}".format(OPTS.word_size, total_size))

    s.save_output()
    
if OPTS.create_bist:
    import bist
    b = bist.bist(addr_size=s.addr_size, 
                  data_size=OPTS.word_size, 
                  delay = OPTS.bist_delay)

    b.save_output()

OPTS.check_lvsdrc = True


end_openram()
print_time("End",datetime.datetime.now(), start_time)


