
""" This is the setup script for ST 28nm.  """

import sys
import os

TECHNOLOGY = "cmos28fdsoi_gold"
AMC_TECH=os.path.abspath(os.environ.get("AMC_TECH"))
DRCLVS_HOME="/gpfs/gibbs/pi/manohar/tech/ST/cmos28fdsoi_29/PDK_STM_cmos28FDSOI_RF_6U1x_2T8x_LB/2.9-07/DATA"
os.environ["DRCLVS_HOME"] = DRCLVS_HOME
os.environ["SPICE_MODEL_DIR"] = "{0}/cmos28fdsoi_gold/models/st28soi.sp".format(AMC_TECH)
LOCAL = "{0}/..".format(os.path.dirname(__file__)) 
sys.path.append("{0}/{1}".format(LOCAL,TECHNOLOGY))

