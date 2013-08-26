# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 CERN
# Author: Pawel Szostek (pawel.szostek@cern.ch)
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

from __future__ import print_function
#from dependable_file import DependableFile
import os
import global_mod
import logging
from module import Module
from tools import ise
from tools import modelsim
from tools import quartus
from util import path as path_mod
from dep_file import DepFile, File


class SourceFile(DepFile):
    cur_index = 0

    def __init__(self, path, module, library=None):
        from dep_file import DepFile
        assert isinstance(path, basestring)
        assert isinstance(module, Module)
        self.library = library
        DepFile.__init__(self,
                         file_path=path,
                         module=module,
                         include_paths=module.include_dirs[:])


    def gen_index(self):
        self.__class__.cur_index = self.__class__.cur_index+1
        return self.__class__.cur_index


class VHDLFile(SourceFile):
    def __init__(self, path, module, library=None, vcom_opt=None):
        SourceFile.__init__(self, path=path, module=module, library=library)
        if not vcom_opt:
            self.vcom_opt = ""
        else:
            self.vcom_opt = vcom_opt

    def _check_encryption(self):
        f = open(self.path, "rb")
        s = f.read(3)
        f.close()
        if(s == b'Xlx'):
            return True
        else:
            return False

    def _create_deps_provides(self):
        if self._check_encryption():
            self.dep_index = SourceFile.gen_index(self)
        else:
            self.dep_provides = list(self._search_packages())
        logging.debug(self.path + " provides " + str(self.dep_provides))

    def _create_deps_requires(self):
        if self._check_encryption():
            self.dep_index = SourceFile.gen_index(self)
        else:
            self.dep_requires = list(self._search_use_clauses())
        logging.debug(self.path + " provides " + str(self.dep_provides))

    def _search_use_clauses(self):
        """
        Reads a file and looks for 'use' clause. For every 'use' with
        non-standard library a tuple (lib, file) is returned in a list.

        """
        # Modification here! global_mod.top_module.action does not
        # get set for top module in time. FIX this

        std_libs = ['std', 'ieee']
        if global_mod.top_module.action == "simulation":
            try:
                if global_mod.top_module.sim_tool == "isim":
                    std_libs = ise.XilinxsiminiReader().get_libraries()
                elif global_mod.top_module.sim_tool == "vsim" or global_mod.top_module.sim_tool == "modelsim":
                    std_libs = modelsim.ModelsiminiReader().get_libraries()
                elif global_mod.top_module.sim_tool == "iverilog":
                    std_libs = modelsim.MODELSIM_STANDARD_LIBS
                else:
                    logging.warning("Could not determine simulation tool. Defaulting to Modelsim")
                    std_libs = modelsim.MODELSIM_STANDARD_LIBS
            except RuntimeError as e:
                logging.error("I/O error: ({0})".format(e.message))
                logging.error("Picking standard Modelsim simulation libraries. Try to fix the error.")
                std_libs = modelsim.MODELSIM_STARDAND_LIBS
        elif global_mod.top_module.action == "synthesis":
            if global_mod.top_module.target == "xilinx":
                std_libs = ise.ISE_STANDARD_LIBS
            elif global_mod.top_module.target == "altera":
                std_libs = quartus.QUARTUS_STANDARD_LIBS

        import re
        try:
            f = open(self.path, "r")
            text = f.readlines()
        except UnicodeDecodeError:
            return []

        use_pattern = re.compile("^[ \t]*use[ \t]+([^; ]+)[ \t]*;.*$")
        lib_pattern = re.compile("([^.]+)\.([^.]+)\.all")

        use_lines = []
        for line in text:
            #identifiers and keywords are case-insensitive in VHDL
            line_lower = line.lower()
            m = re.match(use_pattern, line_lower)
            if m is not None:
                use_lines.append(m.group(1))

        ret = set()
        for line in use_lines:
            m = re.match(lib_pattern, line)
            if m is not None:
                #omit standard libraries
                if (m.group(1)).lower() in std_libs:
                    continue
                if self.library != "work":
                    #if a file is put in a library, `work' points this library
                    new = (self.library.lower(), m.group(2).lower())
                else:
                    new = (m.group(1).lower(), m.group(2).lower())
                #dont add if the tuple is already in the list
                if new in self.dep_provides:
                    continue
                ret.add(new)

        f.close()
        return ret


class VerilogFile(SourceFile):
    def __init__(self, path, module, library=None, vlog_opt=None, include_dirs=None):
        if not library:
            library = "work"
        SourceFile.__init__(self, path=path, module=module, library=library)
        if not vlog_opt:
            self.vlog_opt = ""
        else:
            self.vlog_opt = vlog_opt
        self.include_dirs = []
        if include_dirs:
            self.include_dirs.extend(include_dirs)
        self.include_dirs.append(path_mod.relpath(self.dirname))

    def _create_deps_provides(self):
#        self.dep_requires = self.__search_includes()
#        self.dep_provides = self.name
        self.dep_provides = self.name

    def _create_deps_requires(self):
#        self.dep_requires = self.__search_includes()
#        self.dep_provides = self.name
        if global_mod.top_module.sim_tool == "iverilog":
            deps = self._get_iverilog_dependencies()
            self.dep_requires = deps
        else:
            self.dep_requires = self._search_includes()

    def _get_iverilog_dependencies(self):
           #TODO: Check to see dependencies.list doesn't exist already
        if self.path.endswith(".vh") and global_mod.top_module.sim_tool == "iverilog":
            return []
        inc_dirs = []
        #inc_dirs = global_mod.top_module.include_dirs
        inc_dirs = self.include_dirs
        if global_mod.mod_pool:
            inc_dirs.extend([os.path.relpath(m.path) for m in global_mod.mod_pool])
        inc_dirs = list(set(inc_dirs))
        vlog_opt = global_mod.top_module.vlog_opt
        depFileName = "dependencies.list"
        command = "iverilog -DSIMULATE -Wno-timescale -t null -M" + depFileName
        command += "".join(map(lambda x: " -y"+x, inc_dirs))
        command += "".join(map(lambda x: " -I"+x, inc_dirs))
        # TODO: Have to find a way to handle this cleanly
        if self.rel_path().find("config_romx_llrf4") > -1:
            command += " " + vlog_opt
        else:
            command += " " + vlog_opt + " " + self.rel_path()
            logging.debug("running %s" % command)
            retcode = os.system(command)
            # iverilog_cmd = Popen(command, shell=True, stdin=PIPE,
            #                      stdout=PIPE, close_fds=True)
            # iverilog_cmd.stdout.readlines()
            # iverilog_cmd.wait()
            # retcode = iverilog_cmd.returncode
            print("retcode", retcode)

        if retcode and retcode != 256:
            logging.error("Dependencies not met for %s" % str(self.path))
            logging.debug(command, self.include_dirs, inc_dirs, global_mod.mod_pool)
            quit()
        elif retcode == 256:
            #dependencies met
            pass
        depFile = open(depFileName, "r")
        depFiles = list(set([l.strip() for l in depFile.readlines()]))
        depFile.close()
        return depFiles

    def _search_includes(self):
        import re
        f = open(self.path, "r")
        try:
            text = f.readlines()
        except UnicodeDecodeError:
            return []
        include_pattern = re.compile("^[ \t]*`include[ \t]+\"([^ \"]+)\".*$")
        ret = []
        for line in text:
            #in Verilog and SV identifiers are case-sensitive
            m = re.match(include_pattern, line)
            if m is not None:
                ret.append(m.group(1))
        f.close()
        return ret


class SVFile(VerilogFile):
    pass


class UCFFile(File):
    pass


class TCLFile(File):
    pass


class XISEFile(File):
    pass


class CDCFile(File):
    pass


class SignalTapFile(File):
    pass


class SDCFile(File):
    pass


class QIPFile(File):
    pass


class DPFFile(File):
    pass


# class NGCFile(SourceFile):
#     def __init__(self, path, module):
#         SourceFile.__init__(self, path=path, module=module)
class NGCFile(File):
    pass


class WBGenFile(File):
    pass


class SourceFileSet(set):
    def __init__(self):
        super(SourceFileSet, self).__init__()
        self = []

    def __str__(self):
        return str([str(f) for f in self])

    def add(self, files):
        if isinstance(files, str):
            raise RuntimeError("Expected object, not a string")
        elif files is None:
            logging.debug("Got None as a file.\n Ommiting")
        else:
            try:
                for f in files:
                    super(SourceFileSet, self).add(f)
            except:  # single file, not a list
                super(SourceFileSet, self).add(files)

    def filter(self, type):
        out = SourceFileSet()
        for f in self:
            if isinstance(f, type):
                out.add(f)
        return out

    def inversed_filter(self, type):
        out = SourceFileSet()
        for f in self:
            if not isinstance(f, type):
                out.add(f)
        return out

    def get_libs(self):
        ret = set()
        for file in self:
            try:
                ret.add(file.library)
            except:
                pass
        return ret


class SourceFileFactory:
    def new(self, path, module, library=None, vcom_opt=None, vlog_opt=None, include_dirs=None):
        if path == "/home/pawel/cern/wr-cores/testbench/top_level/gn4124_bfm.svh":
            raise Exception()
        if path is None or path == "":
            raise RuntimeError("Expected a file path, got: "+str(path))
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        tmp = path.rsplit('.')
        extension = tmp[len(tmp)-1]
        logging.debug("add file " + path)

        nf = None
        if extension == 'vhd' or extension == 'vhdl' or extension == 'vho':
            nf = VHDLFile(path=path,
                          module=module,
                          library=library,
                          vcom_opt=vcom_opt)
        elif extension == 'v' or extension == 'vh' or extension == 'vo' or extension == 'vm':
            nf = VerilogFile(path=path,
                             module=module,
                             library=library,
                             vlog_opt=vlog_opt,
                             include_dirs=include_dirs)
        elif extension == 'sv' or extension == 'svh':
            nf = SVFile(path=path,
                        module=module,
                        library=library,
                        vlog_opt=vlog_opt,
                        include_dirs=include_dirs)
        elif extension == 'ngc':
            nf = NGCFile(path=path, module=module)
        elif extension == 'ucf':
            nf = UCFFile(path=path, module=module)
        elif extension == 'cdc':
            nf = CDCFile(path=path, module=module)
        elif extension == 'wb':
            nf = WBGenFile(path=path, module=module)
        elif extension == 'tcl':
            nf = TCLFile(path=path, module=module)
        elif extension == 'xise' or extension == 'ise':
            nf = XISEFile(path=path, module=module)
        elif extension == 'stp':
            nf = SignalTapFile(path=path, module=module)
        elif extension == 'sdc':
            nf = SDCFile(path=path, module=module)
        elif extension == 'qip':
            nf = QIPFile(path=path, module=module)
        elif extension == 'dpf':
            nf = DPFFile(path=path, module=module)
        return nf
