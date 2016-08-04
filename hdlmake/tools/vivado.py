#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 - 2015 CERN
# Author: Pawel Szostek (pawel.szostek@cern.ch)
# Multi-tool support by Javier D. Garcia-Lasheras (javier@garcialasheras.com)
#
# This file is part of Hdlmake.
#
# Hdlmake is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hdlmake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Hdlmake.  If not, see <http://www.gnu.org/licenses/>.
#

"""Module providing support for Xilinx Vivado synthesis"""

import subprocess
import sys
import os
import string
import logging

from hdlmake.action import ActionMakefile
from hdlmake.srcfile import (VHDLFile, VerilogFile, SVFile, UCFFile,
                             NGCFile, XMPFile, XCOFile, BDFile, TCLFile)


VIVADO_STANDARD_LIBS = ['ieee', 'std']


class ToolVivado(ActionMakefile):

    """Class providing the interface for Xilinx Vivado synthesis"""

    TOOL_INFO = {
        'name': 'vivado',
        'id': 'vivado',
        'windows_bin': 'vivado ',
        'linux_bin': 'vivado ',
        'project_ext': 'xpr'
    }

    SUPPORTED_FILES = [UCFFile, NGCFile, XMPFile,
                       XCOFile, BDFile, TCLFile]

    CLEAN_TARGETS = {'clean': ["run.tcl", ".Xil", "*.jou", "*.log",
                               "$(PROJECT).cache", "$(PROJECT).data",
                               "$(PROJECT).runs", "$(PROJECT_FILE)"],
                     'mrproper': ["*.bit", "*.bin"]}

    TCL_CONTROLS = {'create': 'create_project $(PROJECT) ./',
                    'open': 'open_project $(PROJECT_FILE)',
                    'save': '',
                    'close': 'exit',
                    'synthesize': 'reset_run synth_1\n'
                                  'launch_runs synth_1\n'
                                  'wait_on_run synth_1',
                    'translate': '',
                    'map': '',
                    'par': 'reset_run impl_1\n'
                           'launch_runs impl_1\n'
                           'wait_on_run impl_1',
                    'bitstream':
                    'launch_runs impl_1 -to_step write_bitstream\n'
                                 'wait_on_run impl_1',
                    'install_source': '$(PROJECT).runs/impl_1/$(SYN_TOP).bit'}

    def __init__(self):
        super(ToolVivado, self).__init__()

    def detect_version(self, path):
        """Get version from Xilinx Vivado binary program"""
        return 'unknown'

    def _print_syn_tcl(self, top_module, tcl_controls):
        """Create a Xilinx Vivado project"""
        tmp = "set_property {0} {1} [{2}]"
        syn_device = top_module.manifest_dict["syn_device"]
        syn_grade = top_module.manifest_dict["syn_grade"]
        syn_package = top_module.manifest_dict["syn_package"]
        syn_top = top_module.manifest_dict["syn_top"]
        create_new = []
        create_new.append(tcl_controls["create"])
        properties = [
            ['part', syn_device + syn_package + syn_grade, 'current_project'],
            ['target_language', 'VHDL', 'current_project'],
            ['top', syn_top, 'get_property srcset [current_run]']]
        for prop in properties:
            create_new.append(tmp.format(prop[0], prop[1], prop[2]))
        tcl_controls["create"] = "\n".join(create_new)
        super(ToolVivado, self)._print_syn_tcl(top_module, tcl_controls)

    def _print_syn_files(self, fileset):
        """Create a Xilinx Vivado project"""
        self.writeln("define TCL_FILES")
        tmp = "add_files -norecurse {0}"
        tcl = "source {0}"
        for file_aux in fileset:
            if (isinstance(file_aux, VHDLFile) or
                isinstance(file_aux, VerilogFile) or
                isinstance(file_aux, SVFile) or
                isinstance(file_aux, UCFFile) or
                isinstance(file_aux, NGCFile) or
                isinstance(file_aux, XMPFile) or
                isinstance(file_aux, XCOFile) or
                    isinstance(file_aux, BDFile)):
                line = tmp.format(file_aux.rel_path())
            elif isinstance(file_aux, TCLFile):
                line = tcl.format(file_aux.rel_path())
            else:
                continue
            self.writeln(line)
        self.writeln('update_compile_order -fileset sources_1')
        self.writeln('update_compile_order -fileset sim_1')
        self.writeln("endef")
        self.writeln("export TCL_FILES")


