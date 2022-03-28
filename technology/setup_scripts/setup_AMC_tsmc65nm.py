
""" This is the setup script for tsmc 65nm.  """

import sys
import os

TECHNOLOGY = "tsmc65nm"
AMC_TECH=os.path.abspath(os.environ.get("AMC_TECH"))
DRCLVS_HOME=AMC_TECH+"/tsmc65nm/tech"
os.environ["DRCLVS_HOME"] = DRCLVS_HOME
os.environ["SPICE_MODEL_DIR"] = "{0}/tsmc65nm/models/CLN65G_2d5_lk_v1d3.l".format(AMC_TECH)
LOCAL = "{0}/..".format(os.path.dirname(__file__)) 
sys.path.append("{0}/{1}".format(LOCAL,TECHNOLOGY))
