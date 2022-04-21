############################################################################
#
# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
############################################################################


import hierarchy_layout
import hierarchy_spice
import async_verilog
import globals
import debug
import os
from globals import OPTS
from tech import drc, layer

class design(hierarchy_spice.spice, hierarchy_layout.layout, async_verilog.verilog):
    """ Design Class for all modules to inherit the base features.
        Class consisting of a set of modules and instances of these modules """
    name_map = []

    def __init__(self, name):
        self.gds_file = OPTS.AMC_tech + "gds_lib/" + name + ".gds"
        self.sp_file = OPTS.AMC_tech + "sp_lib/" + name + ".sp"

        self.name = name
        self.cell_name = name
        hierarchy_layout.layout.__init__(self, name)
        hierarchy_spice.spice.__init__(self, name, self.cell_name)

        self.setup_drc_constants()
        
        # Check if the name already exists, if so, give an error
        # because each reference must be a unique name.
        # These modules ensure unique names or have no changes if they
        # aren't unique
        ok_list = ["<class 'split.split'>",
                   "<class 'split.split2'>",
                   "<class 'merge.merge'>",
                   "<class 'bitcell.bitcell'>",
                   "<class 'contact.contact'>",
                   "<class 'ptx.ptx'>",
                   "<class 'pinv.pinv'>",
                   "<class 'nand2.nand2'>",
                   "<class 'nor2.nor2'>",
                   "<class 'nand3.nand3'>",
                   "<class 'nor3.nor3'>",
                   "<class 'single_driver.single_driver'>",
                   "<class 'driver.driver'>",
                   "<class 'flipflop.flipflop'>",
                   "<class 'xor2.xor2'>",
                   "<class 'hierarchical_predecode2x4.hierarchical_predecode2x4'>",
                   "<class 'hierarchical_predecode3x8.hierarchical_predecode3x8'>"]
        if name not in design.name_map:
            design.name_map.append(name)
        elif str(self.__class__) in ok_list:
            pass
        else:
            debug.error("Duplicate layout reference name {0} of class {1}. GDS2 requires names be unique.".format(name,self.__class__),-1)
        
    def setup_drc_constants(self):
        """ These are some DRC constants used in many places in the compiler."""
        
        from tech import drc
        
        self.minwidth_tx = drc["minwidth_tx"]
        self.minlength_tx = drc["minlength_channel"]
        self.well_width = drc["minwidth_well"]
        self.active_width = drc["minwidth_active"]
        self.poly_width = drc["minwidth_poly"]
        self.m1_width = drc["minwidth_metal1"]
        self.m2_width = drc["minwidth_metal2"]
        self.m3_width = drc["minwidth_metal3"]
        self.via1_width = drc["minwidth_via1"]
        self.contact_width = drc["minwidth_contact"]
        self.well_space = drc["well_to_well"]
        self.implant_space = drc["implant_to_implant"]
        self.poly_space = drc["poly_to_poly"]
        self.poly_minarea = drc["minarea_poly"]        
        self.m1_space = drc["metal1_to_metal1"]
        self.m2_space = drc["metal2_to_metal2"]        
        self.m3_space = drc["metal3_to_metal3"]
        self.active_minarea= drc["minarea_active"]
        self.m1_minarea = drc["minarea_metal1"]
        self.m2_minarea = drc["minarea_metal2"]
        self.m3_minarea = drc["minarea_metal3"]
        self.well_minarea = drc["minarea_well"]
        self.well_enclose_active = drc["well_enclosure_active"]
        self.implant_enclose_active = drc["implant_enclosure_active"]
        self.implant_enclose_body_active = drc["implant_enclosure_body_active"]
        self.implant_enclose_poly = drc["implant_enclosure_poly"]
        self.metal3_enclosure_via2 = drc["metal3_enclosure_via2"]
        self.active_to_body_active = drc["active_to_body_active"]
        self.active_to_active = drc["active_to_active"]
        self.active_extend_contact = drc["active_extend_contact"]
        self.active_enclose_contact = drc["active_enclosure_contact"]
        self.active_enclose_gate = drc["active_enclosure_gate"]
        self.poly_to_active = drc["poly_to_active"]
        self.poly_extend_active = drc["poly_extend_active"]
        self.poly_enclose_contact = drc["poly_enclosure_contact"]
        self.contact_to_gate = drc["contact_to_gate"]
        self.m1_enclose_contact = drc["metal1_enclosure_contact"]
        self.m1_extend_contact = drc["metal1_extend_contact"]
        self.well_extend_active = drc["well_extend_active"]
        self.extra_minarea = drc["minarea_extra_layer"]
        self.extra_enclose = drc["extra_layer_enclosure"]
        
        self.poly_stack=("poly", "contact", "metal1")
        self.m1_stack=("metal1", "via1", "metal2")
        self.m1_rev_stack=("metal2", "via1", "metal1")
        self.m2_stack=("metal2", "via2", "metal3")
        self.m2_rev_stack=("metal3", "via2", "metal2")
        self.m3_stack=("metal3", "via3", "metal4")
        self.m3_rev_stack=("metal4", "via3", "metal3")
        
    def m_pitch(self, metal):
        """ These are some DRC constants for metal pitches used in many places in the compiler."""
        
        import contact
        if metal =="m1":
            contact=contact.m1m2   
        if metal =="m2":
            contact=contact.m2m3   
        if metal =="m3":
            contact=contact.m3m4   

        n=int(metal[-1])
        
        metal_space=max(drc["metal{0}_to_metal{1}".format(n, n)],
                        drc["metal{0}_to_metal{1}".format(n+1, n+1)])
        contact_space=max(contact.width, contact.height)
        
        metal_pitch = metal_space + contact_space
        return metal_pitch


    def via_shift(self, via):
        """ These are some DRC constants for co/via shift used in many places in the compiler."""
        
        import contact
        if via =="co":
            contact=contact.poly  
        if via =="v1":
            contact=contact.m1m2   
        if via =="v2":
            contact=contact.m2m3   
        
        shift=0.5*abs(contact.second_layer_height - contact.first_layer_height)
        return shift

    def get_layout_pins(self,inst):
        """ Return a map of pin locations of the instance offset """
        
        # find the instance
        for i in self.insts:
            if i.name == inst.name:
                break
        else:
            debug.error("Couldn't find instance {0}".format(inst_name),-1)
        inst_map = inst.mod.pin_map
        return inst_map

    def __str__(self):
        """ override print function output """
        
        return "design: " + self.name

    def __repr__(self):
        """ override print function output """
        text="( design: " + self.name + " pins=" + str(self.pins) + " " + str(self.width) + "x" + str(self.height) + " )\n"
        for i in self.objs:
            text+=str(i)+",\n"
        for i in self.insts:
            text+=str(i)+",\n"
        return text
     
