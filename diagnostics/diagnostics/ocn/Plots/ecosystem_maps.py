""" 
Plot module: PM_E_MAPS
plot name:   Ecosystem maps at surface and various depths

classes:
EcosystemMaps:          base class
EcosystemMaps_obs:      defines specific NCL list for model vs. observations plots
EcosystemMaps_control:  defines specific NCL list for model vs. control plots
"""

from __future__ import print_function

import sys

if sys.hexversion < 0x02070000:
    print(70 * "*")
    print("ERROR: {0} requires python >= 2.7.x. ".format(sys.argv[0]))
    print("It appears that you are running python {0}".format(
        ".".join(str(x) for x in sys.version_info[0:3])))
    print(70 * "*")
    sys.exit(1)

import glob
import itertools
import jinja2
import os
import traceback
import shutil

# import ocean ecosystem python plot modules model vs. observations
from ocn_diag import clim_maps_surface, clim_maps_surface_2D, clim_maps_at_depth
from ocn_diag import nutlim_maps_at_depths 
from ocn_diag import model_obs_maps_surface
from ocn_diag import model_obs_maps_at_depths

# import ocean ecosystem python plot modules model vs. control
from ocn_diag import maps_surface_diff, maps_surface_diff_2D, maps_at_depths_diff

# import the helper utility module
from cesm_utils import cesmEnvLib
from diag_utils import diagUtilsLib

# import the plot baseclass module
from ocn_diags_plot_bc import OceanDiagnosticPlot

class EcosystemMaps(OceanDiagnosticPlot):
    """Detailed description of the plot that will show up in help documentation
    """

    def __init__(self):
        super(EcosystemMaps, self).__init__()
        self._name = 'Ecosystem: Maps'
        self._shortname = 'E_MAPS'

    def check_prerequisites(self, env):
        """list and check specific prequisites for this plot.
        """
        super(EcosystemMaps, self).check_prerequisites(env)
        print("  Checking prerequisites for : {0}".format(self.__class__.__name__))

        # copy the remap* files to the workdir
        remapFiles = glob.glob('{0}/remap*'.format(env['ECOPATH']))
        if len(remapFiles) > 0:
            for remapFile in remapFiles:
                rFileList = remapFile.split('/')
                rFile = rFileList[-1]
                shutil.copy2(rmapFile, '{0}/{1}'.format(env['WORKDIR'],rFile))

    def generate_plots(self, env):
        """Put commands to generate plot here!
        """
        print('  Generating diagnostic plots for : {0}'.format(self.__class__.__name__))
        
        # setup of the arg dictionary to pass to the python modules
        self._setup_args(env)
        for script in self._python:
            script(**self._args)

    def convert_plots(self, workdir, imgFormat):
        """Converts plots for this class
        """
        pass

    def _create_html(self, workdir, templatePath, imgFormat):
        """Creates and renders html that is returned to the calling wrapper
        """
        empty = ['','']
        rowList = [0,1,2,3,4,5,6]
        colList = [0,1,2,3,4,5]
        plot_table_s1_t1 = list()
        plot_table_s1_t2 = list()
        plot_table_s1_t3 = list()
        plot_table_s2 = list()

        # initialize the plot tables with the empty values
        for i in colList:
            for j in rowList:
                plot_table_s1_t1[i:j].append(empty)

        for i in colList:
            plot_table_s1_t2.append(empty)
            plot_table_s1_t3.append(empty)

        # replace elements in the plot table arrays with expectedPlots values
        # s1_t1
        for i in rowList:
            for j in colList:
                k = i+j
                rownum, label, image = self._expectedPlots_s1_t1[k]
                if rownum == j:
                    img_file = '{0}.png'.format(image)
                    rc, err_msg = cesmEnvLib.checkFile( '{0}/{1}'.format(workdir, img_file), 'read' )
                    if not rc:
                        plot_table_s1_t1[i:j] = ['{0} - Error'.format(img_file),'']
                    else:
                        plot_table_s1_t1[i:j] = [label, img_file]
        # s1_t2
        for i in colList:
            rownum, label, image = self._expectedPlots_s1_t2[i]
            if rownum == j:
                img_file = '{0}.png'.format(image)
                rc, err_msg = cesmEnvLib.checkFile( '{0}/{1}'.format(workdir, img_file), 'read' )
                if not rc:
                    plot_table_s1_t2[i] = ['{0} - Error'.format(img_file),'']
                else:
                    plot_table_s1_t2[i] = [label, img_file]

        # s1_t3
        for i in colList:
            rownum, label, image = self._expectedPlots_s1_t3[i]
            if rownum == j:
                img_file = '{0}.png'.format(image)
                rc, err_msg = cesmEnvLib.checkFile( '{0}/{1}'.format(workdir, img_file), 'read' )
                if not rc:
                    plot_table_s1_t3[i] = ['{0} - Error'.format(img_file),'']
                else:
                    plot_table_s1_t3[i] = [label, img_file]

        # s2
        num_rows_s2 = len(self._linkNames)+1
        plot_list = list()
        for i in range(len(self._labels)):
            plot_tuple_list = []
            plot_tuple = (0, 'label','{0}:'.format(self._labels[i]))
            plot_tuple_list.append(plot_tuple)
            for j in range(len(self._linkNames)):
                img_file = '{0}_{1}_{2}.png'.format(self._expectedPlots_s2_prefix, self._labels[i], self._linkNames[j])
                rc, err_msg = cesmEnvLib.checkFile( '{0}/{1}'.format(workdir, img_file), 'read' )
                if not rc:
                    plot_tuple = (j+1, self._linkNames[j],'{0} - Error'.format(img_file))
                else:
                    plot_tuple = (j+1, self._linkNames[j], img_file)
                plot_tuple_list.append(plot_tuple)

            print('DEBUG... plot_tuple_list[{0}] = {1}'.format(i, plot_tuple_list))
            plot_table.append(plot_tuple_list)

        # create a jinja2 template object
        templateLoader = jinja2.FileSystemLoader( searchpath=templatePath )
        templateEnv = jinja2.Environment( loader=templateLoader, keep_trailing_newline=False )

        template = templateEnv.get_template( self._template_file )

        # add the template variables
        templateVars = { 'title' : self._name,
                         'cols' : num_cols,
                         'colList' : colList,
                         'rowList' : rowList,
                         'plot_title_s1' : self.plotTitles[0],
                         'plot_title_s2' : self.plotTitles[1],
                         'plot_table_s1_t1' : plot_table_s1_t1,
                         'plot_table_s1_t2' : plot_table_s1_t2,
                         'plot_table_s1_t3' : plot_table_s1_t3,
                         'plot_table_s2' : plot_table_s2,
                         'num_rows_s2' : num_rows_s2
                         }

        # render the html template using the plot tables
        self._html = template.render( templateVars )
        
        return self._html

class EcosystemMaps_obs(EcosystemMaps):

    def __init__(self):
        super(EcosystemMaps_obs, self).__init__()
        self._python = [clim_maps_surface, clim_maps_surface_2D, clim_maps_at_depth,
                        nutlim_maps_at_depths, model_obs_maps_surface, model_obs_maps_at_depths]

        self._expectedPlots_s1_t1 = ((0,'NH4','map_NH4'), (0,'NO3_excess','map_NO3_excess'),
                                    (1,'spCh1','map_spCh1',), (1,'diatCh1','map_diatCh1'), (1,'diazCh1','diazCh1'),
                                    (2,'spC','map_spC',), (2,'diatC','map_diatC'), (2,'diazC','diazC'),
                                    (3,'photoC_sp','map_photoC_sp'), (3,'photoC_diat','map_photoC_diat'), 
                                     (3,'photoC_diaz','map_photoC_diaz'),
                                    (4,'diaz_Nfix','map_diaz_Nfix'), (4,'DENITRIF','map_DENITRIF'), 
                                     (4,'NITRIF','map_NITRIF'), (4,'CaCO3_form','map_CaCO3_form'), (4,'bSi_form','map_bSi_form'),
                                    (5,'IRON_FLUX','map_IRON_FLUX'), (5,'POC_FLUX_IN','map_POC_FLUX_IN'), 
                                     (5,'CaCO3_FLUX_IN','map_CaCO3_FLUX_IN'), (5,'SiO2_FLUX_IN','map_SiO2_FLUX_IN'),
                                    (6,'STF_O2','map_STF_O2'), (6,'FvPER_DIC','map_FvPER_DIC'), (6,'FvICE_DIC','map_FvPER_DIC'))

        self._expectedPlots_s1_t2 = ((0,'sp_nutlim','map_nutlim_sp'), (0,'diat_nutlim','map_nutlim_diat'), (0,'diaz_nutlim','map_nutlim_diaz'))

        self._expectedPlots_s1_t3 = ((0,'pCO2SURF','mod_obs_map_pCO2SURF_0m'), (0,'FG_CO2','mod_obs_map_FG_CO2_0m'), (0,'totCh1','mod_obs_map_totCh1_0m'), 
                                    (0,'photoC_tot','mod_obs_map_photoC_tot_0m'), (0,'phytoC','mod_obs_map_phytoC_0m'), (0,'phyto_mu','mod_obs_map_phyto_mu_0m'))

        self._plotTitles = ['Lat, Lon', 'Ecosystem: Maps at Depth (with obs where applicable']

        self._labels = ['NO3','PO4','SiO3','O2','DIC','ALK','Fe']
        self._linkNames = ['0m', '50m', '200m', '500m', '1000m', '2000m', '3000m', '4000m']
        self._expectedPlots_s2_prefix = 'mod_obs_map'

        self._template_file = 'ecosystem_maps.tmpl'
    
    def _setup_args(self, env):
        self._args = {'case':env["CASE"], 'yrstart':env["YEAR0"], 'yrend':env["YEAR1"], 
                      'POPDIAGPY':True, 'yroffset':env["YROFFSET"], 'WORKDIRPY':env["WORKDIR"], 
                      'mgrid': env["RESOLUTION"], 'ODATADIR': env["ECODATADIR"]}
        

class EcosystemMaps_control(EcosystemMaps):

    def __init__(self):
        super(EcosystemMaps_control, self).__init__()
        self._python = [maps_surface_diff, maps_surface_diff_2D, maps_at_depths_diff]

    
    def _setup_args(self, env):
        self._args = {'case':env["CASE"], 'yrstart':env["YEAR0"], 'yrend':env["YEAR1"], 
                      'POPDIAGPY':True, 'yroffset':env["YROFFSET"], 'WORKDIRPY':env["WORKDIR"], 
                      'mgrid': env["RESOLUTION"], 'ODATADIR': env["ECODATADIR"]}
