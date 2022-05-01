# See LICENSE for licensing information.
#
# Copyright (c) 2016-2021 Regents of the University of California and The Board
# of Regents for the Oklahoma Agricultural and Mechanical College
# (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
from hierarchy_design import hierarchy_design
import utils
import contact
from tech import GDS, layer
from tech import preferred_directions
from tech import cell_properties as props
from globals import OPTS
import re
import debug


class design(hierarchy_design):
    """
    This is the same as the hierarchy_design class except it contains
    some DRC/layer constants and analytical models for other modules to reuse.
    """

    def __init__(self, name, cell_name=None, prop=None):
        # This allows us to use different GDS/spice circuits for hard cells instead of the default ones
        # Except bitcell names are generated automatically by the globals.py setup_bitcells routines
        # depending on the number of ports.

        if OPTS.mode == "sync" and name in props.names:
            if type(props.names[name]) is list:
                num_ports = OPTS.num_rw_ports + OPTS.num_r_ports + OPTS.num_w_ports - 1
                cell_name = props.names[name][num_ports]
            else:
                cell_name = props.names[name]

        elif not cell_name:
            cell_name = name
        super().__init__(name, cell_name)

        # This means it is a custom cell.
        # It could have properties and not be a hard cell too (e.g. dff_buf)
        if prop and prop.hard_cell:
            # The pins get added from the spice file, so just check
            # that they matched here
            debug.check(prop.port_names == self.pins,
                        "Custom cell pin names do not match spice file:\n{0} vs {1}".format(prop.port_names, self.pins))
            self.add_pin_indices(prop.port_indices)
            self.add_pin_names(prop.port_map)
            self.add_pin_types(prop.port_types)


            (width, height) = utils.get_libcell_size(self.cell_name,
                                                     GDS["unit"],
                                                     layer[prop.boundary_layer])
            self.pin_map = utils.get_libcell_pins(self.pins,
                                                  self.cell_name,
                                                  GDS["unit"])

            # Convert names back to the original names
            # so that copying will use the new names
            for pin_name in self.pin_map:
                for index1, pin in enumerate(self.pin_map[pin_name]):
                    self.pin_map[pin_name][index1].name = self.get_original_pin_name(pin.name)

            self.width = width
            self.height = height

        if OPTS.mode == "sync":
            self.setup_multiport_constants()

            try:
                from tech import power_grid
                self.supply_stack = power_grid
            except ImportError:
                # if no power_grid is specified by tech we use sensible defaults
                # Route a M3/M4 grid
                self.supply_stack = self.m3_stack

    def check_pins(self):
        for pin_name in self.pins:
            pins = self.get_pins(pin_name)
            for pin in pins:
                print(pin_name, pin)

    @classmethod
    def setup_drc_constants(design):
        """
        These are some DRC constants used in many places
        in the compiler.
        """
        from tech import drc
        design.well_extend_active = None
        design.well_enclose_active = None

        # Make some local rules for convenience
        from tech import drc
        for rule in drc.keys():
            # Single layer width rules
            match = re.search(r"minwidth_(.*)", rule)
            if match:
                if match.group(1) == "active_contact":
                    setattr(design, "contact_width", drc(match.group(0)))
                else:
                    setattr(design, match.group(1) + "_width", drc(match.group(0)))

            # Single layer area rules
            match = re.search(r"minarea_(.*)", rule)
            if match:
                setattr(design, match.group(0), drc(match.group(0)))

            # Single layer spacing rules
            match = re.search(r"(.*)_to_(.*)", rule)
            if match and match.group(1) == match.group(2):
                setattr(design, match.group(1) + "_space", drc(match.group(0)))
            elif match and match.group(1) != match.group(2):
                if match.group(2) == "poly_active":
                    setattr(design, match.group(1) + "_to_contact",
                            drc(match.group(0)))
                else:
                    setattr(design, match.group(0), drc(match.group(0)))

            match = re.search(r"(.*)_enclose_(.*)", rule)
            if match:
                setattr(design, match.group(0), drc(match.group(0)))
            else:
                match = re.search(r"(.*)_enclose", rule)
                if match:
                    setattr(design, match.group(0), drc(match.group(0)))

            match = re.search(r"(.*)_extend_(.*)", rule)
            if match:
                setattr(design, match.group(0), drc(match.group(0)))

        # Create the maximum well extend active that gets used
        # by cells to extend the wells for interaction with other cells
        from tech import layer
        if design.well_extend_active is None:
            design.well_extend_active = 0
            if "nwell" in layer:
                design.well_extend_active = max(design.well_extend_active, design.nwell_extend_active)
            if "pwell" in layer:
                design.well_extend_active = max(design.well_extend_active, design.pwell_extend_active)

        if design.well_enclose_active is None:
            # The active offset is due to the well extension
            if "pwell" in layer:
                design.pwell_enclose_active = drc("pwell_enclose_active")
            else:
                design.pwell_enclose_active = 0
            if "nwell" in layer:
                design.nwell_enclose_active = drc("nwell_enclose_active")
            else:
                design.nwell_enclose_active = 0
            # Use the max of either so that the poly gates will align properly
            design.well_enclose_active = max(design.pwell_enclose_active,
                                           design.nwell_enclose_active,
                                           design.active_space)

    @classmethod
    def debug_constants(design):
        for key, value in design.__dict__.items():
            print("{}: {}".format(key, value))

    @classmethod
    def setup_layer_constants(design):
        """
        These are some layer constants used
        in many places in the compiler.
        """

        from tech import layer_indices
        import tech
        for layer_id in layer_indices:
            key = "{}_stack".format(layer_id)

            # Set the stack as a local helper
            try:
                layer_stack = getattr(tech, key)
                setattr(design, key, layer_stack)
            except AttributeError:
                pass

            key = "{}_rev_stack".format(layer_id)

            # Set the reverse stack as a local helper
            try:
                layer_stack = getattr(tech, key)
                setattr(design, key, layer_stack)
            except AttributeError:
                pass

            # Skip computing the pitch for non-routing layers
            if layer_id in ["active", "nwell"]:
                continue

            # Async and Sync design currently calculate different pitch values
            # Should be merged later
            if OPTS.mode == "async":
                setattr(design,
                        "{}_pitch".format(layer_id),
                        design.old_compute_pitch(layer_id))
                setattr(design,
                        "{}_nonpref_pitch".format(layer_id),
                        design.old_compute_pitch(layer_id))
            else:
                # Add the pitch
                setattr(design,
                        "{}_pitch".format(layer_id),
                        design.compute_pitch(layer_id, True))

                # Add the non-preferrd pitch (which has vias in the "wrong" way)
                setattr(design,
                        "{}_nonpref_pitch".format(layer_id),
                        design.compute_pitch(layer_id, False))

        if OPTS.mode == "async":
            # Set DRC contants for co/via shift used in async compiler
            for via in ["co", "v1", "v2"]:
                setattr(design,
                        "{}_via_shift".format(via),
                        design.via_shift(via))

        if False:
            from tech import preferred_directions
            print(preferred_directions)
            from tech import layer_indices
            for name in layer_indices:
                if name == "active":
                    continue
                try:
                    print("{0} width {1} space {2}".format(name,
                                                           getattr(design, "{}_width".format(name)),
                                                           getattr(design, "{}_space".format(name))))

                    print("pitch {0} nonpref {1}".format(getattr(design, "{}_pitch".format(name)),
                                                         getattr(design, "{}_nonpref_pitch".format(name))))
                except AttributeError:
                    pass
            import sys
            sys.exit(1)

    @staticmethod
    def via_shift(via):
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

    @staticmethod
    def compute_pitch(layer, preferred=True):
        """
        This is the preferred direction pitch
        i.e. we take the minimum or maximum contact dimension
        """
        # Find the layer stacks this is used in
        from tech import layer_stacks
        pitches = []
        for stack in layer_stacks:
            # Compute the pitch with both vias above and below (if they exist)
            if stack[0] == layer:
                pitches.append(design.compute_layer_pitch(stack, preferred))
            if stack[2] == layer:
                pitches.append(design.compute_layer_pitch(stack[::-1], True))

        return max(pitches)

    @staticmethod
    def old_compute_pitch(layer):
        """
        Computes pitch. Async design currently needs this pitch calculation,
        should be merged later after more discussion.
        """
        from tech import drc
        import contact
        if layer =="m1":
            contact = contact.m1m2
            layers = ["m1", "m2"]
        elif layer =="m2":
            contact = contact.m2m3
            layers = ["m2", "m3"]
        elif layer =="m3":
            contact = contact.m3m4
            layers = ["m3", "m4"]
        else:
            return 0

        # For m1, should get max of m1_to_m1 and m2_to_m2
        metal_space=max(drc["{0}_to_{1}".format(layers[0], layers[0])],
                drc["{0}_to_{1}".format(layers[1], layers[1])])
        contact_space=max(contact.width, contact.height)
        metal_pitch = metal_space + contact_space
        return metal_pitch

    @staticmethod
    def get_preferred_direction(layer):
        return preferred_directions[layer]

    @staticmethod
    def compute_layer_pitch(layer_stack, preferred):

        (layer1, via, layer2) = layer_stack
        try:
            if layer1 == "poly" or layer1 == "active":
                contact1 = getattr(contact, layer1 + "_contact")
            else:
                contact1 = getattr(contact, layer1 + "_via")
        except AttributeError:
            contact1 = getattr(contact, layer2 + "_via")

        if preferred:
            if preferred_directions[layer1] == "V":
                contact_width = contact1.first_layer_width
            else:
                contact_width = contact1.first_layer_height
        else:
            if preferred_directions[layer1] == "V":
                contact_width = contact1.first_layer_height
            else:
                contact_width = contact1.first_layer_width
        layer_space = getattr(design, layer1 + "_space")

        #print(layer_stack)
        #print(contact1)
        pitch = contact_width + layer_space

        return utils.round_to_grid(pitch)

    def setup_multiport_constants(self):
        """
        These are contants and lists that aid multiport design.
        Ports are always in the order RW, W, R.
        Port indices start from 0 and increment.
        A first RW port will have clk0, csb0, web0, addr0, data0
        A first W port (with no RW ports) will be: clk0, csb0, addr0, data0

        """
        total_ports = OPTS.num_rw_ports + OPTS.num_w_ports + OPTS.num_r_ports

        # These are the read/write port indices.
        self.readwrite_ports = []
        # These are the read/write and write-only port indices
        self.write_ports = []
        # These are the write-only port indices.
        self.writeonly_ports = []
        # These are the read/write and read-only port indices
        self.read_ports = []
        # These are the read-only port indices.
        self.readonly_ports = []
        # These are all the ports
        self.all_ports = list(range(total_ports))

        # The order is always fixed as RW, W, R
        port_number = 0
        for port in range(OPTS.num_rw_ports):
            self.readwrite_ports.append(port_number)
            self.write_ports.append(port_number)
            self.read_ports.append(port_number)
            port_number += 1
        for port in range(OPTS.num_w_ports):
            self.write_ports.append(port_number)
            self.writeonly_ports.append(port_number)
            port_number += 1
        for port in range(OPTS.num_r_ports):
            self.read_ports.append(port_number)
            self.readonly_ports.append(port_number)
            port_number += 1

    def analytical_power(self, corner, load):
        """ Get total power of a module  """
        total_module_power = self.return_power()
        for inst in self.insts:
            total_module_power += inst.mod.analytical_power(corner, load)
        return total_module_power

design.setup_drc_constants()
design.setup_layer_constants()

# Prints drc and layer constants for debugging
if False:
    design.debug_constants()
    import sys
    sys.exit(1)
