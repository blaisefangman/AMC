
""" This is the setup script for scn3me_subm tech """

import sys
import os

TECHNOLOGY = "scn3me_subm"
AMC_TECH=os.path.abspath(os.environ.get("AMC_TECH"))
DRCLVS_HOME=AMC_TECH+"/async/scn3me_subm/tech"
os.environ["DRCLVS_HOME"] = DRCLVS_HOME
os.environ["SPICE_MODEL_DIR"] = "{0}/async/scn3me_subm/models/on_c5n.mod".format(AMC_TECH)
LOCAL = "{0}/..".format(os.path.dirname(__file__)) 
sys.path.append("{0}/{1}".format(LOCAL,TECHNOLOGY))
