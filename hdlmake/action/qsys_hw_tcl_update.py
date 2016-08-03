#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016 AUT
# Author: William Kamp (william.kamp@aut.ac.nz)
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

"""Module providing an way to update Altera Qsys HW TCL files.
NOTE: This module is provided by the SKA telescope collaboration
and need a rework to fully fit into the HDLMake structure. """

import hdlmake.new_dep_solver as dep_solver
import os
import shutil
import logging

from .action import Action


class QsysHwTclUpdate(Action):

    """Class providing methods to update a set of Altera Qsys HW TCL files"""

    def __init__(self, *args):
        super(QsysHwTclUpdate, self).__init__(*args)

    def qsys_hw_tcl_update(self):
        """Build the fileset for synthesis and update the HW TCL files"""
        file_set = self.build_file_set(
            self.get_top_module().manifest_dict["syn_top"])
        file_list = dep_solver.make_dependency_sorted_list(file_set)
        files_str = [os.path.relpath(f_listed.path) for f_listed in file_list]

        file_tcl = []
        for file_aux in files_str:
            fname = os.path.split(file_aux)[1]
            file_tcl.append("add_fileset_file %s VHDL PATH %s"
                            % (fname, file_aux))

        # mark the last file as the top level file.
        file_tcl[-1] += " TOP_LEVEL_FILE"
        file_tcl.append("\n")

        hw_tcl_filename = self.get_top_module().manifest_dict[
            "hw_tcl_filename"]

        infile = open(hw_tcl_filename, "r")
        inserted = True
        out_lines = []
        for line in infile.readlines():
            if line.startswith("add_fileset QUARTUS_SYNTH"):
                inserted = False
            if line.startswith("add_fileset SIM_VHDL"):
                inserted = False
            if line.startswith("add_fileset_file"):
                if not inserted:
                    out_lines.append("\n".join(file_tcl))
                    inserted = True
            else:
                out_lines.append(line)

        infile.close()

        hw_tcl_filename_backup = hw_tcl_filename + ".bak"
        shutil.copy2(hw_tcl_filename, hw_tcl_filename_backup)
        logging.info("Old hw.tcl file backed up to %s", hw_tcl_filename_backup)

        logging.info("Updating the file list in %s", hw_tcl_filename)

        outfile = open(hw_tcl_filename, "w")
        outfile.writelines(out_lines)
        outfile.close()
