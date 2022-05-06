# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.


import os
from custom_cell_properties import cell_properties
from design_rules import *

""" File containing the process technology parameters for SCMOS 3me, subm, 600nm. """

info={}
info["name"]="scn3me_subm"
info["body_tie_down"] = 0
info["has_pwell"] = True
info["has_nwell"] = True
info["has_pimplant"] = True
info["has_nimplant"] = True
info["tx_dummy_poly"] = False
info["well_contact_extra"] = False
info["foundry_cell"] = False
info["add_well_tap"] = False
info["tx_is_subckt"] = False

#GDS file info
GDS={}
# gds units
GDS["unit"]=(0.001,1e-6)  
# default label zoom
GDS["zoom"] = 0.5

###################################################
# Custom cell properties
###################################################
cell_properties = cell_properties()

###################################################
# Interconnect stacks
###################################################
poly_stack = ("poly", "contact", "m1")
active_stack = ("active", "contact", "m1")
m1_stack = ("m1", "via1", "m2")
m2_stack = ("m2", "via2", "m3")

m1_rev_stack = ("m2", "via1", "m1")
m2_rev_stack = ("m3", "via2", "m2")

layer_indices = {"poly": 0,
                 "active": 0,
                 "nwell": 0, # Added nwell and pwell otherwise errors
                 "pwell": 0, # are caused in pin_layout.py
                 "m1": 1,
                 "m2": 2,
                 "m3": 3}

# The FEOL stacks get us up to m1
feol_stacks = [poly_stack,
                       active_stack]
# The BEOL stacks are m1 and up
beol_stacks = [m1_stack,
               m2_stack]

layer_stacks = feol_stacks + beol_stacks

preferred_directions = {"poly": "V",
                        "active": "V",
                        "m1": "H",
                        "m2": "V",
                        "m3": "H",
                        "m4": "V"}

###################################################
##GDS Layer Map
###################################################

# create the GDS layer map
#order of pins in the following lists matters
amc_layer_names = ["m1", "via1", "m2", "via2", "m3", "via3", "m4"]
tech_layer_names = ["Metal1", "Via1", "Metal2", "Via2", "Metal3", "Via3", "Metal4"]

layer={} 
layer["vt"]             = (-1,0) 
layer["poly_contact"]   = (47,0) 
layer["pwell"]          = (41,0) 
layer["nwell"]          = (42,0) 
layer["active"]         = (43,0) 
layer["pimplant"]       = (44,0)
layer["nimplant"]       = (45,0)
layer["poly"]           = (46,0) 
layer["active_contact"] = (48,0)
layer["m1"]         = (49,0) 
layer["via1"]           = (50,0) 
layer["m2"]         = (51,0) 
layer["via2"]           = (61,0) 
layer["m3"]         = (62,0)
layer["via3"]           = (-1,0)
layer["m4"]         = (-1,0) 
layer["boundary"]       = (83,0)
layer["m1pin"]          = (49, 0)
layer["m2pin"]          = (51, 0)
layer["m3pin"]          = (62, 0) 
layer["m4pin"]          = (-1, 0)
layer["polypin"]        = (46, 0)  
layer["extra_layer"]    = (-1,0)
layer[None]             = (-1, 0)
GDS["label_dataType"]   = 0
GDS["pin_dataType"]     = 0
###################################################
##END GDS Layer Map
###################################################

# Layer names for external PDKs
layer_names = {}
layer_names["active"]  = "active"
layer_names["pwell"]   = "pwell"
layer_names["nwell"]   = "nwell"
layer_names["nimplant"]= "nimplant"
layer_names["pimplant"]= "pimplant"
layer_names["poly"]    = "poly" 
layer_names["poly_contact"] = "poly_contact"
layer_names["active_contact"] = "active_contact"
layer_names["m1"]      = "metal1"
layer_names["via1"]    = "via1"
layer_names["m2"]      = "metal2"
layer_names["via2"]    = "via2"
layer_names["m3"]      = "metal3"
layer_names["via3"]    = "via3"
layer_names["m4"]      = "metal4"
layer_names["text"]    = "text" 
layer_names["boundary"]= "boundary"

###################################################
##DRC/LVS Rules Setup
###################################################

#technology parameter
parameter={}
parameter["min_tx_size"] = 1.2
parameter["beta"] = 2 

drclvs_home=os.environ.get("DRCLVS_HOME")

drc = design_rules("scn3me_subm")
#grid size is 1/2 a lambda
drc["grid"]=0.15

### DRC/LVS test set_up  ####
drc["drc_rules"] = drclvs_home+"/calibreDRC_scn3me_subm.rul"
drc["lvs_rules"] = drclvs_home+"/calibreLVS_scn3me_subm.rul"
drc["drc_custom_rules"] = ""
drc["custom_options"] = ""
drc["lvs_custom_rules"] = ""
drc["layer_map"] = os.environ.get("AMC_TECH")+"/scn3me_subm/layers.map"
drc["drc_golden"] = ""
drc["drcExtraLayoutPaths"] = ""
        	      					
### minwidth_tx with contact (no dog bone transistors) ####
drc["minwidth_tx"] = 1.2
drc["minlength_channel"] = 0.6

### WELL RULES ####
# 1.4 Minimum spacing between wells of different type (if both are drawn) 
drc["pwell_to_nwell"] = 0
drc["well_to_well"] = 1.8
# 1.1 Minimum width 
drc["minwidth_well"] = 3.6
drc["minwidth_nwell"] = 3.6
drc["minwidth_pwell"] = 3.6
#Not a rule
drc["minarea_well"] = 0
drc["minarea_pwell"] = 0
drc["minarea_nwell"] = 0

### POLY RULES ####                                                                      
# 3.1 Minimum width 
drc["minwidth_poly"] = 0.6
# 3.2 Minimum spacing over active
drc["poly_to_poly"] = 0.9
# 3.3 Minimum gate extension of active 
drc["poly_extend_active"] = 0.6
# ??
drc["poly_to_poly_contact"] = 1.2
# Not a rule
drc["active_enclose_gate"] = 0.0
# 3.2.a Minimum spacing over field poly
drc["poly_to_field_poly"] = 0.9
# 3.5 Minimum field poly to active 
drc["poly_to_active"] = 0.3
# Not a rule
drc["minarea_poly"] = 0.0
#not a rule
drc["minarea_poly_merge"] = 0.0

### ACTIVE RULES ####
# ??
drc["active_to_body_active"] = 1.2  
# 2.1 Minimum width 
drc["minwidth_active"] = 0.9
# 2.2 Minimum spacing
drc["active_to_active"] = 0.9
# 2.3 Source/drain active to well edge 
drc["well_enclose_active"] = 1.8
drc["pwell_enclose_active"] = 1.8
drc["nwell_enclose_active"] = 1.8
# Reserved for asymmetric enclosures
drc["well_extend_active"] = 1.8
# Not a rule
drc["minarea_active"] = 0.0

### VT layer RULES ####
#Not a rule
drc["vt_enclose_active"] = 0
#Not a rule
drc["vt_extend_active"] = 0
#Not a rule
drc["minarea_vt"] = 0

### extra layer RULES ####
#Not a rule
drc["minarea_extra_layer"] = 0
#Not a rule
drc["extra_layer_enclose"] = 0
#Not a rule
drc["extra_layer_to_extra_layer"] = 0
#Not a rule
drc["extra_layer_to_poly"] = 0


### implant (select) RULES ####
# 4.1 Minimum select spacing to channel of transistor 
drc["implant_to_channel"] = 0.9
# 4.2 Minimum select overlap of active
drc["implant_enclose_active"] = 0.6
# Not a rule
drc["implant_enclose_body_active"] = 0.6
# 4.3 Minimum select overlap of contact  
drc["implant_enclose_poly_contact"] = 0.3
# Not a rule
drc["implant_enclose_poly"] = 0
#Not a rule
drc["implant_to_active"] = 0
#Not a rule
drc["implant_to_gate"] = 0.0
# Not a rule
drc["implant_to_poly_contact"] = 0
drc["implant_to_active_contact"] = 0
# Not a rule
drc["implant_to_implant"] = 0
# Not a rule
drc["minwidth_implant"] = 0
drc["minwidth_nimplant"] = 0
drc["minwidth_pimplant"] = 0
# Not a rule
drc["minarea_implant"] = 0

### CONTACT RULES ####
# 6.1 Exact contact size
drc["minwidth_poly_contact"] = 0.6
drc["minwidth_active_contact"] = 0.6
# 5.3 Minimum contact spacing
drc["poly_contact_to_poly_contact"] = 0.9                    
drc["active_contact_to_active_contact"] = 0.9                    
# 6.2.b Minimum active overlap 
drc["active_enclose_poly_contact"] = 0.3
drc["active_enclose_active_contact"] = 0.3
# Reserved for asymmetric enclosure
drc["active_extend_poly_contact"] = 0.3
drc["active_extend_active_contact"] = 0.3
# 5.2.b Minimum poly overlap 
drc["poly_enclose_poly_contact"] = 0.3
# Reserved for asymmetric enclosures
drc["poly_extend_poly_contact"] = 0.3
# Reserved for other technologies
drc["poly_contact_to_gate"] = 0.6
# 5.4 Minimum spacing to gate of transistor
drc["poly_contact_to_poly"] = 0.6

### Metal1 RULES ####        
# 7.1 Minimum width 
drc["minwidth_m1"] = 0.9
#Not a rule m1pin = metal1
drc["minwidth_m1pin"] = 0
# 7.2 Minimum spacing 
drc["m1_to_m1"] = 0.9
# 7.3 Minimum overlap of any contact 
drc["m1_enclose_poly_contact"] = 0.3
drc["m1_enclose_active_contact"] = 0.3
# Reserved for asymmetric enclosure
drc["m1_extend_poly_contact"] = 0.3
drc["m1_extend_active_contact"] = 0.3
# 8.3 Minimum overlap by metal1 
drc["m1_enclose_via1"] = 0.3                
# Reserve for asymmetric enclosures
drc["m1_extend_via1"] = 0.3
# Not a rule
drc["minarea_m1"] = 0

### VIA1 RULES ####
# 8.1 Exact size 
drc["minwidth_via1"] = 0.6
# 8.2 Minimum via1 spacing 
drc["via1_to_via1"] = 0.6

### Metal2 RULES ####
# 9.1 Minimum width
drc["minwidth_m2"] = 0.9
#Not a rule
drc["minwidth_m2pin"] = 0
# 9.2 Minimum spacing 
drc["m2_to_m2"] = 0.9
# 9.3 Minimum overlap of via1 
drc["m2_extend_via1"] = 0.3
# Reserved for asymmetric enclosures
drc["m2_enclose_via1"] = 0.3
# 14.3 Minimum overlap by metal2
drc["m2_extend_via2"] = 0.3
# Reserved for asymmetric enclosures
drc["m2_enclose_via2"] = 0.3
# Not a rule
drc["minarea_m2"] = 0

### VIA2 RULES ####
# 14.2 Exact size
drc["minwidth_via2"] = 0.6
# 14.2 Minimum spacing
drc["via2_to_via2"] = 0.9    

### Metal3 RULES ####
# 15.1 Minimum width
drc["minwidth_m3"] = 1.5
#Not a rule
drc["minwidth_m3pin"] = 0
# 15.2 Minimum spacing to metal3
drc["m3_to_m3"] = 0.9
# 15.3 Minimum overlap of via 2
drc["m3_extend_via2"] = 0.6
# Reserved for asymmetric enclosures
drc["m3_enclose_via2"] = 0.6
# Not a rule
drc["m3_extend_via3"] = 0
# Not a rule
drc["m3_enclose_via3"] = 0 
# Not a rule
drc["minarea_m3"] = 0

### VIA3 RULES ####
# Not a rule
drc["minwidth_via3"] = 0
# Not a rule
drc["via3_to_via3"] = 0    

### Metal4 RULES ####
# Not a rule
drc["minwidth_m4"] = 0
# Not a rule
drc["minwidth_m4pin"] = 0
# Not a rule
drc["m4_to_m4"] = 0
# Not a rule
drc["m4_extend_via3"] = 0
# Not a rule
drc["m4_enclose_via3"] = 0
# Not a rule
drc["minarea_m4"] = 0



###################################################
##END DRC/LVS Rules
###################################################

###################################################
##Spice Simulation Parameters
###################################################

# spice model info
spice={}
spice["nmos"]="n"
spice["pmos"]="p"

# Not a property in this tech
spice["poly_bias"] = -1
# This is a map of corners to model files
SPICE_MODEL_DIR=os.environ.get("SPICE_MODEL_DIR")

#spice stimulus related variables
spice["inv_delay"] = 0.14                    # Estimated inverter gate delay [ns]
spice["input_cap"] = 10                     # Input capacitance of split cell (Din,ctrl,addr) [fF] 
spice["feasible_period"] = 5                # estimated feasible period in ns
spice["supply_voltages"] = [4.5, 5.0, 5.5]  # Supply voltage corners in [V]
spice["nom_supply_voltage"] = 5.0           # Nominal supply voltage in [V]
spice["rise_time"] = 0.05                   # Rise time in [ns]
spice["fall_time"] = 0.05                   # Fall time in [ns]
spice["temperatures"] = [0, 25, 100]        # Temperature corners (oC)
spice["nom_temperature"] = 25               # Nominal temperature (oC)

#sram signal names
spice["vdd_name"] = "vdd"
spice["gnd_name"] = "gnd"
spice["control_signals"] = ["reset", "R", "W", "RW", "ACK", "WREQ", "WACK", "RREQ", "RACK"]
spice["data_name"] = "DATA"
spice["addr_name"] = "ADDR"
spice["minwidth_tx"] = drc["minwidth_tx"]
spice["channel"] = drc["minlength_channel"]

###################################################
##END Spice Simulation Parameters
###################################################

###################################################
# Technology Tool Preferences
###################################################
drc_name = "calibre"
lvs_name = "calibre"
pex_name = "calibre"