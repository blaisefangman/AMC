# See LICENSE for licensing information.
#
# Copyright (c) 2016-2021 Regents of the University of California and The Board
# of Regents for the Oklahoma Agricultural and Mechanical College
# (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
import debug
from tech import GDS, drc
from vector import vector
from tech import layer#, layer_indices
import math


class pin_layout:
    """
    A class to represent a rectangular design pin. It is limited to a
    single shape.
    """

    def __init__(self, name, rect, layer_name_pp):
        self.name = name
        # repack the rect as a vector, just in case
        if type(rect[0])==vector:
            self._rect = rect
        else:
            self._rect = [vector(rect[0]),vector(rect[1])]
        # snap the rect to the grid
        self._rect = [x.snap_to_grid() for x in self.rect]
        
        debug.check(self.width() > 0, "Zero width pin.")
        debug.check(self.height() > 0, "Zero height pin.")

        # These are the valid pin layers
        # valid_layers = {x: layer[x] for x in layer_indices.keys()}
        valid_layers = layer

        # if it's a string, use the name
        if type(layer_name_pp) == str:
            self._layer = layer_name_pp
        # else it is required to be a lpp
        else:
            for (layer_name, lpp) in valid_layers.items():
                if not lpp:
                    continue
                if self.same_lpp(layer_name_pp, lpp):
                    self._layer = layer_name
                    break

            else:
                try:
                    from tech import layer_override
                    from tech import layer_override_name
                    if layer_override[name]:
                        self.lpp = layer_override[name]
                        self.layer = "pwellp"
                        self._recompute_hash()
                        return
                except:
                    debug.error("Layer {} is not a valid routing layer in the tech file.".format(layer_name_pp), -1)
        
        self.lpp = layer[self.layer]
        self._recompute_hash()

    @property
    def layer(self):
        return self._layer

    @layer.setter
    def layer(self, l):
        self._layer = l
        self._recompute_hash()

    @property
    def rect(self):
        return self._rect

    @rect.setter
    def rect(self, r):
        self._rect = r
        self._recompute_hash()

    def _recompute_hash(self):
        """ Recompute the hash for our hash cache """
        self._hash = hash(repr(self))

    def __str__(self):
        """ override print function output """
        return "({} layer={} ll={} ur={})".format(self.name,self.layer,self.rect[0],self.rect[1])

    def __repr__(self):
        """ override print function output """
        return "({} layer={} ll={} ur={})".format(self.name,self.layer,self.rect[0],self.rect[1])

    def __eq__(self, other):
        """ Check if these are the same pins for duplicate checks """
        if isinstance(other, self.__class__):
            return (self.name==other.name and self.layer==other.layer and self.rect == other.rect)
        else:
            return False    

    def overlaps(self, other):
        """ Check if a shape overlaps with a rectangle  """
        
        ll = self.rect[0]
        ur = self.rect[1]
        oll = other.rect[0]
        our = other.rect[1]
        # Start assuming no overlaps
        x_overlaps = False
        y_overlaps = False
        
        # check if self is within other x range
        if (ll.x >= oll.x and ll.x <= our.x) or (ur.x >= oll.x and ur.x <= our.x):
            x_overlaps = True
        # check if other is within self x range
        if (oll.x >= ll.x and oll.x <= ur.x) or (our.x >= ll.x and our.x <= ur.x):
            x_overlaps = True
            
        # check if self is within other y range
        if (ll.y >= oll.y and ll.y <= our.y) or (ur.y >= oll.y and ur.y <= our.y):
            y_overlaps = True
        # check if other is within self y range
        if (oll.y >= ll.y and oll.y <= ur.y) or (our.y >= ll.y and our.y <= ur.y):
            y_overlaps = True

        return x_overlaps and y_overlaps
    
    def height(self):
        """ Return height. Abs is for pre-normalized value."""
        return abs(self.rect[1].y-self.rect[0].y)
    
    def width(self):
        """ Return width. Abs is for pre-normalized value."""
        return abs(self.rect[1].x-self.rect[0].x)

    def normalize(self):
        """ Re-find the LL and UR points after a transform """
        
        (first,second)=self.rect
        ll = vector(min(first[0],second[0]),min(first[1],second[1]))
        ur = vector(max(first[0],second[0]),max(first[1],second[1]))
        self.rect=[ll,ur]
        
    def transform(self,offset,mirror,rotate):
        """ Transform with offset, mirror and rotation to get the absolute pin location. 
            We must then re-find the ll and ur. The master is the cell instance. """
        
        (ll,ur) = self.rect
        if mirror=="MX":
            ll=ll.scale(1,-1)
            ur=ur.scale(1,-1)
        elif mirror=="MY":
            ll=ll.scale(-1,1)
            ur=ur.scale(-1,1)
        elif mirror=="XY":
            ll=ll.scale(-1,-1)
            ur=ur.scale(-1,-1)
            
        if rotate==90:
            ll=ll.rotate_scale(-1,1)
            ur=ur.rotate_scale(-1,1)
        elif rotate==180:
            ll=ll.scale(-1,-1)
            ur=ur.scale(-1,-1)
        elif rotate==270:
            ll=ll.rotate_scale(1,-1)
            ur=ur.rotate_scale(1,-1)

        self.rect=[offset+ll,offset+ur]
        self.normalize()

    def center(self):
        return vector(0.5*(self.rect[0].x+self.rect[1].x),0.5*(self.rect[0].y+self.rect[1].y))

    def cx(self):
        """ Center x """
        return 0.5*(self.rect[0].x+self.rect[1].x)

    def cy(self):
        """ Center y """
        return 0.5*(self.rect[0].y+self.rect[1].y)
    
    # The four possible corners
    def ll(self):
        """ Lower left point """
        return self.rect[0]

    def ul(self):
        """ Upper left point """
        return vector(self.rect[0].x,self.rect[1].y)

    def lr(self):
        """ Lower right point """
        return vector(self.rect[1].x,self.rect[0].y)

    def ur(self):
        """ Upper right point """
        return self.rect[1]
    
    # The possible y edge values 
    def uy(self):
        """ Upper y value """
        return self.rect[1].y

    def by(self):
        """ Bottom y value """
        return self.rect[0].y

    # The possible x edge values
    def lx(self):
        """ Left x value """
        return self.rect[0].x
    
    def rx(self):
        """ Right x value """
        return self.rect[1].x
    
    # The edge centers
    def rc(self):
        """ Right center point """
        return vector(self.rect[1].x,0.5*(self.rect[0].y+self.rect[1].y))

    def lc(self):
        """ Left center point """
        return vector(self.rect[0].x,0.5*(self.rect[0].y+self.rect[1].y))
    
    def uc(self):
        """ Upper center point """
        return vector(0.5*(self.rect[0].x+self.rect[1].x),self.rect[1].y)

    def bc(self):
        """ Bottom center point """
        return vector(0.5*(self.rect[0].x+self.rect[1].x),self.rect[0].y)

    def cc(self):
        """ center point """
        return vector(0.5*(self.rect[0].x+self.rect[1].x),0.5*(self.rect[0].y+self.rect[1].y))

    def gds_write_file(self, newLayout):
        """Writes the pin shape and label to GDS"""
        
        debug.info(4, "writing pin (" + str(self.layer) + "):" 
                   + str(self.width()) + "x" + str(self.height()) + " @ " + str(self.ll()))

        # Try to use the pin layer if it exists, otherwise
        # use the regular layer
        try:
            (pin_layer_num, pin_purpose) = layer[self.layer + "p"]
        except KeyError:
            (pin_layer_num, pin_purpose) = layer[self.layer]
        (layer_num, purpose) = layer[self.layer]

        # Try to use a global pin purpose if it exists,
        # otherwise, use the regular purpose
        try:
            from tech import pin_purpose as global_pin_purpose
            pin_purpose = global_pin_purpose
        except ImportError:
            pass

        try:
            from tech import label_purpose
            try:
                from tech import layer_override_purpose
                if pin_layer_num in layer_override_purpose:
                    layer_num = layer_override_purpose[pin_layer_num][0]
                    label_purpose = layer_override_purpose[pin_layer_num][1]
            except:
                pass
        except ImportError:
            label_purpose = purpose

        newLayout.addBox(layerNumber=layer_num,
                         dataType=purpose,
                         offsetInMicrons=self.ll(),
                         width=self.width(),
                         height=self.height(),
                         center=False)

        # Draw a second pin shape too if it is different
        if not self.same_lpp((pin_layer_num, pin_purpose), (layer_num, purpose)):
            newLayout.addBox(layerNumber=pin_layer_num,
                             purposeNumber=pin_purpose,
                             offsetInMicrons=self.ll(),
                             width=self.width(),
                             height=self.height(),
                             center=False)
        # Add the text in the middle of the pin.
        # This fixes some pin label offsetting when GDS gets
        # imported into Magic.
        try:
            zoom = GDS["zoom"]
        except KeyError:
            zoom = None
        newLayout.addText(text=self.name,
                          layerNumber=layer_num,
                          purposeNumber=label_purpose,
                          offsetInMicrons=self.ll(),
                          magnification=zoom,
                          rotate=None)
    
    def same_lpp(self, lpp1, lpp2):
        """
        Check if the layers and purposes are the same.
        Ignore if purpose is a None.
        """
        if lpp1[1] == None or lpp2[1] == None:
            return lpp1[0] == lpp2[0]

        return lpp1[0] == lpp2[0] and lpp1[1] == lpp2[1]
