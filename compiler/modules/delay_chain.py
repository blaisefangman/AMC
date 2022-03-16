############################################################################
#
# BSD 3-Clause License (See LICENSE.OR for licensing information)
# Copyright (c) 2016-2019 Regents of the University of California 
# and The Board of Regents for the Oklahoma Agricultural and 
# Mechanical College (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
############################################################################


import design
import debug
import contact
import utils
from tech import drc
from vector import vector
from pinv import pinv
from math import ceil


class delay_chain(design.design):
    """ Generate a delay chain with the given number of stages"""

    def __init__(self, num_inv, num_stage, name="delay_chain"):
        design.design.__init__(self, name)

        self.num_inv = num_inv
        self.num_stage = num_stage
        
        self.inv = pinv()
        self.add_mod(self.inv)

        if self.num_inv <self.num_stage:
            debug.error("number of inverters must be greater than or equal to number of stages!",-1)
        
        self.add_pins()
        self.create_module()
        self.route_inv()
        self.width = (self.num_even_stage+self.final_stage)*self.inv.width + 4*self.m_pitch("m1")+contact.m1m2.height
        self.height = self.stage_size*self.inv.height
        self.add_layout_pins()
        self.offset_all_coordinates()

    def add_pins(self):
        """ Add pins for delay_chain, order of the pins is important """
        
        self.add_pin_list(["in", "out", "vdd", "gnd"])

    def create_module(self):
        """ Generate a list of inverters"""
        
        self.stage_size = int(ceil(self.num_inv/self.num_stage))
        
        if self.num_inv%self.num_stage == 0:
            self.num_even_stage = self.num_stage
            self.final_stage_size = 0
            self.final_stage = 0
        else:
            if self.num_inv-(self.stage_size*self.num_stage) < self.stage_size:
                self.num_even_stage = self.num_stage
                self.final_stage_size = self.num_inv - (self.num_even_stage*self.stage_size)
                self.final_stage = 1
            else :
                self.num_even_stage = self.num_stage -1
                self.stage_size = self.stage_size+1
                self.final_stage_size = abs(self.num_inv - (self.num_even_stage*self.stage_size))
                self.final_stage = 1
        
        self.inv_inst = {}
        self.index =0
        for i in range(self.num_even_stage):
            for j in range(self.stage_size):
                if j%2:
                    mirror="MX"
                    off = (i*self.inv.width, (j+1)*self.inv.height)
                else:
                    mirror="R0"
                    off = (i*self.inv.width, j*self.inv.height)
                
                self.index= i*self.stage_size+j

                self.inv_inst[self.index]=self.add_inst(name="delay_inv{0}{1}".format(i,j),
                                                        mod=self.inv,
                                                        offset= off,
                                                        mirror=mirror)
                
                if j == 0 and i ==0:
                    self.connect_inst(["in", "in{0}_{1}".format(i, j+1), "vdd", "gnd"])
                
                elif (i== self.num_even_stage-1) and (j== self.stage_size-1):
                    if self.num_stage == 1:
                        self.connect_inst(["in{0}_{1}".format(j-1, 1), "out", "vdd", "gnd"])
                    else:
                        self.connect_inst(["in{0}_{1}".format(j, i), "out", "vdd", "gnd"])                  
                
                elif (i== 0):
                    if (self.final_stage and j <self.final_stage_size+1):
                        self.connect_inst(["in{0}_{1}".format(j-1, (self.num_even_stage+1)), "in{0}_{1}".format(j, 1), "vdd", "gnd"])                
                    else:
                        self.connect_inst(["in{0}_{1}".format(j-1, self.num_even_stage), "in{0}_{1}".format(j, 1), "vdd", "gnd"])                

                else:
                    self.connect_inst(["in{0}_{1}".format(j, i), "in{0}_{1}".format(j, i+1), "vdd", "gnd"])        

        for j in range(self.final_stage_size):
            if j%2:
                mirror="MX"
                off = (self.num_even_stage*self.inv.width, (j+1)*self.inv.height)
            else:
                mirror="R0"
                off = (self.num_even_stage*self.inv.width, j*self.inv.height)
            
            self.index=self.num_even_stage*self.stage_size+j

            self.inv_inst[self.index] = self.add_inst(name="delay_inv{0}{1}".format(self.num_even_stage,j),
                                                      mod=self.inv,
                                                      offset= off,
                                                      mirror=mirror)

            self.connect_inst(["in{0}_{1}".format(j, self.num_even_stage), "in{0}_{1}".format(j, self.num_even_stage+1), "vdd", "gnd"])

    def route_inv(self):
        """ Add metal routing for each of the fanout stages """
        
        l = int(len(self.inv_inst))-1
        for j in range(self.final_stage_size):
            pin1 = self.inv_inst[l-self.final_stage_size+1+j].get_pin("Z")
            pin2 = self.inv_inst[j+1].get_pin("A")
            mid_pos1=vector(pin1.rx()+self.m_pitch("m1"), pin1.lc().y)
            mid_pos2=vector(mid_pos1.x, (j+1)*self.inv.height)
            mid_pos3=vector(pin2.lx()-self.m_pitch("m1"), mid_pos2.y)
            mid_pos4=vector(mid_pos3.x, pin2.lc().y)
            self.add_path("metal2", [mid_pos1, mid_pos2, mid_pos3, mid_pos4])
            self.add_via_center(self.m1_stack, mid_pos1, rotate=90)
            self.add_via_center(self.m1_stack, mid_pos4, rotate=90)
            self.add_path("metal1", [pin1.lc(), mid_pos1])
            self.add_path("metal1", [ mid_pos4, pin2.lc()])
        
        for j in range(self.stage_size-self.final_stage_size-1):
            pin1 = self.inv_inst[l-self.stage_size+1+j].get_pin("Z")
            pin2 = self.inv_inst[self.final_stage_size+1+j].get_pin("A")
            mid_pos1=vector(pin1.rx()+self.m_pitch("m1"), pin1.lc().y)
            mid_pos2=vector(mid_pos1.x, (j+self.final_stage_size+1)*self.inv.height)
            mid_pos3=vector(pin2.lx()-self.m_pitch("m1"), mid_pos2.y)
            mid_pos4=vector(mid_pos3.x, pin2.lc().y)
            self.add_path("metal2", [mid_pos1, mid_pos2, mid_pos3, mid_pos4])
            self.add_via_center(self.m1_stack, mid_pos1, rotate=90)
            self.add_via_center(self.m1_stack, mid_pos4, rotate=90)
            self.add_path("metal1", [pin1.lc(), mid_pos1])
            self.add_path("metal1", [mid_pos4, pin2.lc()])
        
        for i in range(self.stage_size):
            for j in range(self.num_even_stage-1):
                pin1 = self.inv_inst[i+j*self.stage_size].get_pin("Z")
                pin2 = self.inv_inst[self.stage_size+i+j*self.stage_size].get_pin("A")
                yoff = min (pin1.by(), pin2.by())
                height= abs(pin1.by()-pin2.by())+self.m1_width
                off = (pin2.lx()-self.m1_space, yoff)
                self.add_rect(layer="metal1", offset= off, width=self.m1_space, height=height)
        for i in range(self.final_stage_size):
            pin1 = self.inv_inst[i+(self.num_even_stage-1)*self.stage_size].get_pin("Z")
            pin2 = self.inv_inst[i+self.num_even_stage*self.stage_size].get_pin("A")
            yoff = min (pin1.by(), pin2.by())
            height= abs(pin1.by()-pin2.by())+self.m1_width
            off = (pin2.lx()-self.m1_space, yoff)
            self.add_rect(layer="metal1", offset= off, width=self.m1_space, height=height)
            
    def add_layout_pins(self):
        """ Add vdd and gnd rails and the input/output. Connect the gnd rails internally on
             the top end with no input/output to obstruct."""

        
        # input is A pin of first inverter
        a_pin = self.inv_inst[0].get_pin("A")
        self.add_layout_pin(text="in",
                            layer=a_pin.layer,
                            offset=a_pin.ll(),
                            width=a_pin.width(),
                            height=a_pin.height())

        # output is Z pin of last inverter
        z_pin = self.inv_inst[int(len(self.inv_inst))-1-self.final_stage_size].get_pin("Z")
        self.add_layout_pin(text="out",
                            layer=z_pin.layer,
                            offset=z_pin.ll(),
                            width=z_pin.width(),
                            height=z_pin.height())

        #gnd = -2pitch, vdd = -3pitch
        for i in range(2):
            xoff=self.inv_inst[0].get_pin("A").lx()-0.5*self.m2_width
            self.add_rect(layer="metal2", 
                          offset = (xoff-(2+i)*self.m_pitch("m1"),0),
                          width=self.m2_width,
                          height=self.height)
        for i in range(self.stage_size):
            if i%2:
                pin = self.inv_inst[i].get_pin("gnd")
                self.add_path("metal1", [(xoff-2*self.m_pitch("m1"), pin.lc().y), pin.lc()])
                self.add_via_center(self.m1_stack, (xoff-2*self.m_pitch("m1")+0.5*self.m2_width, pin.lc().y), rotate=90)

            else:
                pin = self.inv_inst[i].get_pin("vdd")
                self.add_path("metal1", [(xoff-3*self.m_pitch("m1"), pin.lc().y), pin.lc()])
                self.add_via_center(self.m1_stack, (xoff-3*self.m_pitch("m1")+0.5*self.m2_width, pin.lc().y), rotate=90)

            #first gnd
            pin = self.inv_inst[0].get_pin("gnd")
            self.add_path("metal1", [(xoff-2*self.m_pitch("m1"), pin.lc().y), pin.lc()])
            self.add_via_center(self.m1_stack, (xoff-2*self.m_pitch("m1")+0.5*self.m2_width, pin.lc().y), rotate=90)
        
        power_pin=["gnd", "vdd"]
        for i in range(2):
            pin = self.inv_inst[0].get_pin(power_pin[i])
            self.add_path("metal1", [(xoff-(2+i)*self.m_pitch("m1"), pin.lc().y), pin.lc()])
            self.add_via_center(self.m1_stack, (xoff-(2+i)*self.m_pitch("m1")+0.5*self.m2_width, pin.lc().y), rotate=90)
            self.add_layout_pin(text=power_pin[i],
                                layer=pin.layer,
                                offset=pin.ll(),
                                width=pin.width(),
                                height=pin.height())

