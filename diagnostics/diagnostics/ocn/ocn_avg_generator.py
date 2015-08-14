#!/usr/bin/env python2
"""Generate ocean climatology average files for a given CESM case 

This script provides an interface between:
1. the CESM case environment,
2. the ocean diagnostics environment defined in XML files,
3. the Python package for averaging operations in parallel

It is called from the run script and resides in the $CCSMROOT/postprocessing/cesm-env2
__________________________
Created on October 28, 2014

Author: CSEG <cseg@cgd.ucar.edu>
"""

from __future__ import print_function
import sys

# check the system python version and require 2.7.x or greater
if sys.hexversion < 0x02070000:
    print(70 * '*')
    print('ERROR: {0} requires python >= 2.7.x. '.format(sys.argv[0]))
    print('It appears that you are running python {0}'.format(
        '.'.join(str(x) for x in sys.version_info[0:3])))
    print(70 * '*')
    sys.exit(1)

# import core python modules
import argparse
import getopt
import os
import re
import traceback

# import local modules for postprocessing
from cesm_utils import cesmEnvLib
from diag_utils import diagUtilsLib

# import the MPI related modules
from asaptools import partition, simplecomm, vprinter, timekeeper

# import the pyaverager
from pyaverager import specification, PyAverager

#=====================================================
# commandline_options - parse any command line options
#=====================================================
def commandline_options():
    """Process the command line arguments.
    """
    parser = argparse.ArgumentParser(
        description='ocn_avg_generator: CESM wrapper python program for ocean climatology packages.')

    parser.add_argument('--backtrace', action='store_true',
                        help='show exception backtraces as extra debugging '
                        'output')

    parser.add_argument('--debug', nargs=1, required=False, type=int, default=0,
                        help='debugging verbosity level output: 0 = none, 1 = minimum, 2 = maximum. 0 is default')

    parser.add_argument('--caseroot', nargs=1, required=True, 
                        help='fully quailfied path to case root directory')

    parser.add_argument('--control-run', action='store_true', default=False,
                        help='Controls whether or not to process climatology files for a control run using the settings in the caseroot env_diags_[component].xml files.')

    options = parser.parse_args()

    # check to make sure CASEROOT is a valid, readable directory
    if not os.path.isdir(options.caseroot[0]):
        err_msg = ' ERROR: ocn_avg_generator.py invalid option --caseroot {0}'.format(options.caseroot[0])
        raise OSError(err_msg)

    return options


#============================================================
# buildOcnAvgList - build the list of averages to be computed
#============================================================
def buildOcnAvgList(start_year, stop_year, avgFileBaseName, tavgdir, debugMsg):
    """buildOcnAvgList - build the list of averages to be computed
    by the pyAverager. Checks if the file exists or not already.

    Arguments:
    start_year (string) - starting year
    stop_year (string) - ending year
    avgFileBaseName (string) - avgFileBaseName (tavgdir/case.[stream].)

    Return:
    avgList (list) - list of averages to be passed to the pyaverager
    """

    avgList = []
    padding = 4
#    year = int(start_year)

    # start with the annual averages for all variables
#    while year <= int(stop_year):
#        # check if file already exists before appending to the avgList
#        syear = str(year)
#        zyear = syear.zfill(padding)
#        avgFile = '{0}.{1}.nc'.format(avgFileBaseName, zyear)
#        debugMsg('avgFile = {0}'.format(avgFile), header=True)
#        rc, err_msg = cesmEnvLib.checkFile(avgFile, 'read')
#        if not rc: 
#            avgList.append('ya:{0}'.format(zyear))
#        year += 1

    # prepend the years with 0's
#    zstart_year = start_year.zfill(padding)
#    zstop_year = stop_year.zfill(padding)
    zstart_year = start_year
    zstop_year = stop_year

    # check if mavg file already exists
    avgFile = '{0}/mavg.{1}-{2}.nc'.format(tavgdir, zstart_year, zstop_year)
    debugMsg('mavgFile = {0}'.format(avgFile))
    rc, err_msg = cesmEnvLib.checkFile(avgFile, 'read')
    if not rc:
        avgList.append('mavg:{0}:{1}'.format(zstart_year, zstop_year))

    # check if tavg file already exists
    avgFile = '{0}/tavg.{1}-{2}.nc'.format(tavgdir, zstart_year, zstop_year)
    debugMsg('tavgFile = {0}'.format(avgFile))
    rc, err_msg = cesmEnvLib.checkFile(avgFile, 'read')
    if not rc:
        avgList.append('tavg:{0}:{1}'.format(zstart_year, zstop_year))

    # the following are for timeseries.... TODO - check if timeseries is specified
    # append the MOC and monthly MOC files
##    avgList.append('moc:{0}:{1}'.format(int(start_year), int(stop_year)))
##    avgList.append('mocm:{0}:{1}'.format(int(start_year), int(stop_year)))
    
    # append the horizontal mean concatenation
##    avgList.append('hor.meanConcat:{0}:{1}'.format(int(start_year), int(stop_year)))

    debugMsg('exit buildOcnAvgList avgList = {0}'.format(avgList))
    return avgList

#========================================================================
# callPyAverager - create the climatology files by calling the pyAverager
#========================================================================
def callPyAverager(start_year, stop_year, in_dir, htype, tavgdir, case_prefix, averageList, varList, debugMsg):
    """setup the pyAverager specifier class with specifications to create
       the climatology files in parallel.

       Arguments:
       start_year (integer) - starting year for diagnostics
       stop_year (integer) - ending year for diagnositcs
       in_dir (string) - input directory with either history time slice or variable time series files
       htype (string) - 'series' or 'slice' depending on input history file type
       tavgdir (string) - output directory for climatology files
       case_prefix (string) - input filename prefix
       averageList (list) - list of averages to be created
       varList (list) - list of variables. Note: an empty list implies all variables.
    """
    #TODO ask Sheri if these are still necessary fro the ocean
    mean_diff_rms_obs_dir = '/glade/p/work/mickelso/PyAvg-OMWG-obs/obs/'
    region_nc_var = 'REGION_MASK'
    regions={1:'Sou',2:'Pac',3:'Ind',6:'Atl',8:'Lab',9:'Gin',10:'Arc',11:'Hud',0:'Glo'}
    region_wgt_var = 'TAREA'
    obs_dir = '/glade/p/work/mickelso/PyAvg-OMWG-obs/obs/'
    obs_file = 'obs.nc'
    reg_obs_file_suffix = '_hor_mean_obs.nc'

    wght = False
    ncfrmt = 'netcdf'
    serial = False
    clobber = True
    date_pattern = 'yyyymm-yyyymm'
    suffix = 'nc'

    debugMsg('calling specification.create_specifier with following args', header=True)
    debugMsg('... in_directory = {0}'.format(in_dir), header=True)
    debugMsg('... out_directory = {0}'.format(tavgdir), header=True)
    debugMsg('... prefix = {0}'.format(case_prefix), header=True)
    debugMsg('... suffix = {0}'.format(suffix), header=True)
    debugMsg('... date_pattern = {0}'.format(date_pattern), header=True)
    debugMsg('... hist_type = {0}'.format(htype), header=True)
    debugMsg('... avg_list = {0}'.format(averageList), header=True)
    debugMsg('... weighted = {0}'.format(wght), header=True)
    debugMsg('... ncformat = {0}'.format(ncfrmt), header=True)
    debugMsg('... varlist = {0}'.format(varList), header=True)
    debugMsg('... serial = {0}'.format(serial), header=True)
    debugMsg('... clobber = {0}'.format(clobber), header=True)
    debugMsg('... mean_diff_rms_obs_dir = {0}'.format(mean_diff_rms_obs_dir), header=True)
    debugMsg('... region_nc_var = {0}'.format(region_nc_var), header=True)
    debugMsg('... regions = {0}'.format(regions), header=True)
    debugMsg('... region_wgt_var = {0}'.format(region_wgt_var), header=True)
    debugMsg('... obs_dir = {0}'.format(obs_dir), header=True)
    debugMsg('... obs_file = {0}'.format(obs_file), header=True)
    debugMsg('... reg_obs_file_suffix = {0}'.format(reg_obs_file_suffix), header=True)

    try: 
        pyAveSpecifier = specification.create_specifier(
            in_directory = in_dir,
            out_directory = tavgdir,
            prefix = case_prefix,
            suffix=suffix,
            date_pattern=date_pattern,
            hist_type = htype,
            avg_list = averageList,
            weighted = wght,
            ncformat = ncfrmt,
            varlist = varList,
            serial = serial,
            clobber = clobber,
            mean_diff_rms_obs_dir = mean_diff_rms_obs_dir,
            region_nc_var = region_nc_var,
            regions = regions,
            region_wgt_var = region_wgt_var,
            obs_dir = obs_dir,
            obs_file = obs_file,
            reg_obs_file_suffix = reg_obs_file_suffix)
    except Exception as error:
        print(str(error))
        traceback.print_exc()
        sys.exit(1)

    try:
        debugMsg("calling run_pyAverager")
        PyAverager.run_pyAverager(pyAveSpecifier)
    except Exception as error:
        print(str(error))
        traceback.print_exc()
        sys.exit(1)

#=========================================================================
# createClimFiles - create the climatology files by calling the pyAverager
#=========================================================================
def createClimFiles(start_year, stop_year, in_dir, htype, tavgdir, case, inVarList, debugMsg):
    """setup the pyAverager specifier class with specifications to create
       the climatology files in parallel.

       Arguments:
       start_year (integer) - starting year for diagnostics
       stop_year (integer) - ending year for diagnositcs
       in_dir (string) - input directory with either history time slice or variable time series files
       htype (string) - 'series' or 'slice' depending on input history file type
       tavgdir (string) - output directory for averages
       case (string) - case name
       inVarList (list) - if empty, then create climatology files for all vars, RHO, SALT and TEMP
    """
    # create the list of averages to be computed
    avgFileBaseName = '{0}/{1}.pop.h'.format(tavgdir,case)
    case_prefix = '{0}.pop.h'.format(case)
    averageList = []

    # create the list of averages to be computed by the pyAverager
    averageList = buildOcnAvgList(start_year, stop_year, avgFileBaseName, tavgdir, debugMsg)

    # if the averageList is empty, then all the climatology files exist with all variables
    if len(averageList) > 0:
        # call the pyAverager with the inVarList
        callPyAverager(start_year, stop_year, in_dir, htype, tavgdir, case_prefix, averageList, inVarList, debugMsg)


#============================================
# initialize_envDict - initialization envDict
#============================================
def initialize_envDict(envDict, caseroot, debugMsg):
    """initialize_main - initialize settings on rank 0 
    
    Arguments:
    envDict (dictionary) - environment dictionary
    caseroot (string) - case root
    debugMsg (object) - vprinter object for printing debugging messages

    Return:
    envDict (dictionary) - environment dictionary
    """
    # setup envDict['id'] = 'value' parsed from the CASEROOT/[env_file_list] files
    env_file_list = ['env_case.xml', 'env_run.xml', 'env_build.xml', 'env_mach_pes.xml', 'env_postprocess.xml', 'env_diags_ocn.xml']
    envDict = cesmEnvLib.readXML(caseroot, env_file_list)

    # debug print out the envDict
    debugMsg('envDict after readXML = {0}'.format(envDict), header=True, verbosity=2)

    # refer to the caseroot that was specified on the command line instead of what
    # is read in the environment as the caseroot may have changed from what is listed
    # in the env xml
    envDict['CASEROOT'] = caseroot

    # add the os.environ['PATH'] to the envDict['PATH']
    envDict['OCNDIAG_PATH'] += os.pathsep + os.environ['PATH']

    # strip the OCNDIAG_ prefix from the envDict entries before setting the 
    # enviroment to allow for compatibility with all the diag routine calls
    envDict = diagUtilsLib.strip_prefix(envDict, 'OCNDIAG_')

    return envDict

#======
# main
#======

def main(options, debugMsg):
    """setup the environment for running the pyAverager in parallel. 

    Arguments:
    options (object) - command line options
    debugMsg (object) - vprinter object for printing debugging messages

    The env_diags_ocn.xml configuration file defines the way the diagnostics are generated. 
    See (website URL here...) for a complete desciption of the env_diags_ocn XML options.
    """

    # initialize the environment dictionary
    envDict = dict()

    # CASEROOT is given on the command line as required option --caseroot
    caseroot = options.caseroot[0]
    debugMsg('caseroot = {0}'.format(caseroot), header=True)

    debugMsg('calling initialize_envDict', header=True)
    envDict = initialize_envDict(envDict, caseroot, debugMsg)

    # specify variables to include in the averages, empty list implies get them all
    varList = []

    # generate the climatology files used for all plotting types using the pyAverager
    debugMsg('calling createClimFiles', header=True)
    tavg_dir = envDict['TAVGDIR'] 
    case_name = envDict['CASE']

    # initialize some variables needed for the pyaverager specifier class
#    start_year = 0
#    stop_year = 1
#    htype = 'series'
#    in_dir = '{0}/ocn/hist'.format(envDict['DOUT_S_ROOT'])

    # get model history file information from the DOUT_S_ROOT archive location
    debugMsg('calling checkHistoryFiles for model case', header=True)
    suffix = 'pop.h.*.nc'
    file_pattern = '.*\.pop\.h\.\d{4,4}-\d{2,2}\.nc'
    start_year, stop_year, in_dir, htype, firstHistoryFile = diagUtilsLib.checkHistoryFiles(
        envDict['GENERATE_TIMESERIES'], envDict['DOUT_S_ROOT'], envDict['CASE'],
        envDict['YEAR0'], envDict['YEAR1'], 'ocn', suffix, file_pattern)
    envDict['YEAR0'] = start_year
    envDict['YEAR1'] = stop_year
    envDict['in_dir'] = in_dir
    envDict['htype'] = htype

    try:
        createClimFiles(envDict['YEAR0'], envDict['YEAR1'], envDict['in_dir'],
                        envDict['htype'], envDict['TAVGDIR'], envDict['CASE'], varList, debugMsg)
    except Exception as error:
        print(str(error))
        traceback.print_exc()
        sys.exit(1)

    # check that the necessary control climotology files exist
    if envDict['MODEL_VS_CONTROL'].upper() == 'TRUE':
        debugMsg('calling checkHistoryFiles for control case', header=True)
        suffix = 'pop.h.*.nc'
        file_pattern = '.*\.pop\.h\.\d{4,4}-\d{2,2}\.nc'
        start_year, stop_year, in_dir, htype, firstHistoryFile = diagUtilsLib.checkHistoryFiles(
            envDict['CNTRLCASE_TIMESERIES'], envDict['CNTRLCASEDIR'], envDict['CNTRLCASE'], 
            envDict['CNTRLYEAR0'], envDict['CNTRLYEAR1'], 'ocn', suffix, file_pattern)
        envDict['CNTRLYEAR0'] = start_year
        envDict['CNTRLYEAR1'] = stop_year
        envDict['cntrl_in_dir'] = in_dir
        envDict['cntrl_htype'] = htype

        try:
            createClimFiles(envDict['CNTRLYEAR0'], envDict['CNTRLYEAR1'], envDict['cntrl_in_dir'],
                            envDict['cntrl_htype'], envDict['CNTRLTAVGDIR'], envDict['CNTRLCASE'], varList, debugMsg)
        except Exception as error:
            print(str(error))
            traceback.print_exc()
            sys.exit(1)


#===================================

if __name__ == "__main__":
    # get commandline options
    options = commandline_options()

    # initialize global vprinter object for printing debug messages
    debugMsg = vprinter.VPrinter(header='', verbosity=0)
    if options.debug:
        header = 'ocn_avg_generator: DEBUG... '
        debugMsg = vprinter.VPrinter(header=header, verbosity=options.debug[0])
    
    try:
        status = main(options, debugMsg)
        debugMsg('*** Successfully completed generating ocean climatology averages ***', header=False)
        sys.exit(status)

##    except RunTimeError as error:
        
    except Exception as error:
        print(str(error))
        if options.backtrace:
            traceback.print_exc()
        sys.exit(1)
