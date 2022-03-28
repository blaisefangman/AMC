
""" This is the setup script for GF 12nm.  """

import sys
import os

TECHNOLOGY = "cmos12lp"
AMC_TECH=os.path.abspath(os.environ.get("AMC_TECH"))
DRCLVS_HOME="{}/cmos12lp/tech".format(AMC_TECH)
os.environ["DRCLVS_HOME"] = DRCLVS_HOME
os.environ["SPICE_MODEL_DIR"] = "{}/cmos12lp/models/12LP_Hspice_STD.lib".format(AMC_TECH)
LOCAL = "{0}/..".format(os.path.dirname(__file__)) 
sys.path.append("{0}/{1}".format(LOCAL,TECHNOLOGY))
