#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 CERN
# Author: Pawel Szostek (pawel.szostek@cern.ch)
# Modified to allow ISim simulation by Lucas Russo (lucas.russo@lnls.br)
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

import os
import string
import logging
import global_mod
from string import Template


class _StaticClassVariable():
    pass

_m = _StaticClassVariable()
_m.initialized = False


class MakefileWriter(object):
    def __init__(self, filename=None):
        self._file = None
        if filename:
            self._filename = filename
        else:
            self._filename = "Makefile"

    def __del__(self):
        if self._file:
            self._file.close()

    def initialize(self):
        if os.path.exists(self._filename):
            if os.path.isfile(self._filename):
                os.remove(self._filename)
            elif os.path.isdir(self._filename):
                os.rmdir(self._filename)

        self._file = open(self._filename, "a+")
        if not _m.initialized:
            self.writeln("########################################")
            self.writeln("#  This file was generated by hdlmake  #")
            self.writeln("#  http://ohwr.org/projects/hdl-make/  #")
            self.writeln("########################################")
            self.writeln()

    def write(self, line=None):
        if not _m.initialized:
            self.initialize()
            _m.initialized = True
        self._file.write(line)

    def writeln(self, text=None):
        if text is None:
            self._file.write("\n")
        else:
            self._file.write(text+"\n")

    def reset_file(self, filename):
        self._file.close()
        self._file = open(filename, "w")

    def generate_remote_synthesis_makefile(self, files, name, cwd, user, server):
        from subprocess import PIPE, Popen
        if name is None:
            import random
            name = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(8))
        whoami = Popen('whoami', shell=True, stdin=PIPE, stdout=PIPE, close_fds=True)
        name = whoami.stdout.readlines()[0].strip() + '/' + name
        user_tmpl = "USER:={0}"
        server_tmpl = "SERVER:={0}"
        ise_path_tmpl = "ISE_PATH:={0}"
        port_tmpl = "PORT:=22"
        remote_name_tmpl = "R_NAME:={0}"
        files_tmpl = "FILES := {0}"

        user_tmpl = user_tmpl.format("$(HDLMAKE_RSYNTH_USER)#take the value from the environment")
        test_tmpl = """__test_for_remote_synthesis_variables:
ifeq (x$(USER),x)
\t@echo "Remote synthesis user is not set.\
You can set it by editing variable USER in the makefile or setting env. variable HDLMAKE_RSYNTH_USER." && false
endif
ifeq (x$(SERVER),x)
\t@echo "Remote synthesis server is not set.\
You can set it by editing variable SERVER in the makefile or setting env. variable HDLMAKE_RSYNTH_SERVER." && false
endif
ifeq (x$(ISE_PATH),x)
\t@echo "Remote synthesis server is not set.\
You can set it by editing variable ISE_PATH in the makefile or setting env. variable HDLMAKE_RSYNTH_ISE_PATH." && false
endif
"""
        if server is None:
            server_tmpl = server_tmpl.format("$(HDLMAKE_RSYNTH_SERVER)#take the value from the environment")
        else:
            server_tmpl = server_tmpl.format(server)

        remote_name_tmpl = remote_name_tmpl.format(name)
        self.initialize()
        self.writeln(user_tmpl)
        self.writeln(server_tmpl)
        self.writeln(ise_path_tmpl.format("$(HDLMAKE_RSYNTH_ISE_PATH)"))
        self.writeln(remote_name_tmpl)
        self.writeln(port_tmpl)
        self.writeln()
        self.writeln(test_tmpl)
        self.writeln("CWD := $(shell pwd)")
        self.writeln("")
        self.writeln(files_tmpl.format(' \\\n'.join([s.rel_path() for s in files])))
        self.writeln("")
        self.writeln("#target for running simulation in the remote location")
        self.writeln("remote: __test_for_remote_synthesis_variables __send __do_synthesis")
        self.writeln("__send_back: __do_synthesis")
        self.writeln("__do_synthesis: __send")
        self.writeln("__send: __test_for_remote_synthesis_variables")
        self.writeln("")

        mkdir_cmd = "ssh $(USER)@$(SERVER) 'mkdir -p $(R_NAME)'"
        rsync_cmd = "rsync -e 'ssh -p $(PORT)' -Ravl $(foreach file, $(FILES), $(shell readlink -f $(file))) $(USER)@$(SERVER):$(R_NAME)"
        send_cmd = "__send:\n\t\t{0}\n\t\t{1}".format(mkdir_cmd, rsync_cmd)
        self.writeln(send_cmd)
        self.writeln("")

        tcl = "run.tcl"
        synthesis_cmd = """__do_synthesis:
ifeq (x$(HDLMAKE_RSYNTH_USE_SCREEN), x1)
\t\tssh -t $(USER)@$(SERVER) 'screen bash -c "cd $(R_NAME)$(CWD) && $(HDLMAKE_RSYNTH_ISE_PATH)/xtclsh {0}"'
else
\t\tssh $(USER)@$(SERVER) 'cd $(R_NAME)$(CWD) && $(HDLMAKE_RSYNTH_ISE_PATH)/xtclsh {0}'
endif
"""
        self.writeln(synthesis_cmd.format(tcl))

        self.writeln()
        send_back_cmd = "sync: \n\t\tcd .. && rsync -av $(USER)@$(SERVER):$(R_NAME)/$(CWD) . && cd $(CWD)"
        self.write(send_back_cmd)
        self.write("\n\n")

        cln_cmd = "cleanremote:\n\t\tssh $(USER)@$(SERVER) 'rm -rf $(R_NAME)'"
        self.writeln("#target for removing stuff from the remote location")
        self.writeln(cln_cmd)
        self.writeln()

    def generate_quartus_makefile(self, top_mod):
        pass

    def generate_ise_makefile(self, top_mod, ise_path):
        makefile_tmplt = Template("""PROJECT := ${project_name}
ISE_CRAP := \
*.b \
${syn_top}_summary.html \
*.tcl \
${syn_top}.bld \
${syn_top}.cmd_log \
*.drc \
${syn_top}.lso \
*.ncd \
${syn_top}.ngc \
${syn_top}.ngd \
${syn_top}.ngr \
${syn_top}.pad \
${syn_top}.par \
${syn_top}.pcf \
${syn_top}.prj \
${syn_top}.ptwx \
${syn_top}.stx \
${syn_top}.syr \
${syn_top}.twr \
${syn_top}.twx \
${syn_top}.gise \
${syn_top}.unroutes \
${syn_top}.ut \
${syn_top}.xpi \
${syn_top}.xst \
${syn_top}_bitgen.xwbt \
${syn_top}_envsettings.html \
${syn_top}_guide.ncd \
${syn_top}_map.map \
${syn_top}_map.mrp \
${syn_top}_map.ncd \
${syn_top}_map.ngm \
${syn_top}_map.xrpt \
${syn_top}_ngdbuild.xrpt \
${syn_top}_pad.csv \
${syn_top}_pad.txt \
${syn_top}_par.xrpt \
${syn_top}_summary.xml \
${syn_top}_usage.xml \
${syn_top}_xst.xrpt \
usage_statistics_webtalk.html \
webtalk.log \
webtalk_pn.xml \
run.tcl

#target for performing local synthesis
local: syn_pre_cmd check_tool
\t\techo "project open $$(PROJECT)" > run.tcl
\t\techo "process run {Generate Programming File} -force rerun_all" >> run.tcl
\t\t${ise_path}/xtclsh run.tcl

check_tool:
\t\t${check_tool}

syn_post_cmd: local
\t\t${syn_post_cmd}

syn_pre_cmd:
\t\t${syn_pre_cmd}

#target for cleaing all intermediate stuff
clean:
\t\trm -f $$(ISE_CRAP)
\t\trm -rf xst xlnx_auto_*_xdb iseconfig _xmsgs _ngo

#target for cleaning final files
mrproper:
\t\trm -f *.bit *.bin *.mcs

.PHONY: mrproper clean syn_pre_scipt syn_post_cmd local check_tool

""")
        self.initialize()
        if top_mod.syn_pre_cmd:
            syn_pre_cmd = top_mod.syn_pre_cmd
        else:
            syn_pre_cmd = ''

        if top_mod.syn_post_cmd:
            syn_post_cmd = top_mod.syn_post_cmd
        else:
            syn_post_cmd = ''

        if top_mod.force_tool:
            ft = top_mod.force_tool
            check_tool = """python $(HDLMAKE_HDLMAKE_PATH)/hdlmake _conditioncheck --tool {tool} --reference {reference} --condition "{condition}"\\
|| (echo "{tool} version does not meet condition: {condition} {reference}" && false)
""".format(tool=ft[0],
                condition=ft[1],
                reference=ft[2])
        else:
            check_tool = ''

        makefile_text = makefile_tmplt.substitute(syn_top=top_mod.syn_top,
                                  project_name=top_mod.syn_project,
                                  ise_path=ise_path,
                                  check_tool=check_tool,
                                  syn_pre_cmd=syn_pre_cmd,
                                  syn_post_cmd=syn_post_cmd)
        self.write(makefile_text)
        for f in top_mod.incl_makefiles:
            if os.path.exists(f):
                self.write("include %s\n" % f)

    def generate_fetch_makefile(self, modules_pool):
        rp = os.path.relpath
        self.initialize()
        self.write("#target for fetching all modules stored in repositories\n")
        self.write("fetch: ")
        self.write(' \\\n'.join(["__"+m.basename+"_fetch" for m in modules_pool if m.source in (SVN, GIT)]))
        self.write("\n\n")

        for module in modules_pool:
            basename = module.basename
            if module.source == SVN:
                self.write("__"+basename+"_fetch:\n")
                self.write("\t\tmkdir -p %s\n" % rp(module.fetchto))
                self.write("\t\tPWD=$(shell pwd) ")
                self.write("cd " + rp(module.fetchto) + ' && ')
                c = "svn checkout {0}{1}"
                if module.revision:
                    c = c.format(module.url, "@"+module.revision)
                else:
                    c = c.format(module.url, "")
                self.write(c)
                self.write("; cd $(PWD) \n\n")

            elif module.source == GIT:
                self.write("__"+basename+"_fetch:\n")
                self.write("\t\tmkdir -p %s\n" % rp(module.fetchto))
                self.write("\t\t")
                self.write("PWD=$(shell pwd) ")
                self.write("cd " + rp(module.fetchto) + ' && ')
                self.write("if [ -d " + basename + " ]; then cd " + basename + ' && ')
                self.write("git pull ")
                if module.revision:
                    self.write(" && git checkout " + module.revision + '; ')
                self.write("else git clone " + module.url + ' && ')
                if module.revision:
                    self.write("cd " + basename + " && git checkout " + module.revision + '; fi; ')
                self.write("cd $(PWD) \n\n")

    def generate_iverilog_makefile(self, fileset, top_module, modules_pool):
        from srcfile import VerilogFile
        #open the file and write the above preambule (part 1)
        self.initialize()
        import global_mod
#        for m in global_mod.mod_pool:
        for f in global_mod.top_module.incl_makefiles:
            self.writeln("include " + f)
        libs = set(f.library for f in fileset)
        target_list = []
        for vl in fileset.filter(VerilogFile):
            rel_dir_path = os.path.dirname(vl.rel_path())
            if rel_dir_path:
                rel_dir_path = rel_dir_path + '/'
            target_name = os.path.join(rel_dir_path+vl.purename)
            target_list.append(target_name)
#            dependencies_string = ' '.join([f.rel_path() for f in vl.depends_on if (f.name != vl.name) and not f.name
            dependencies_string = ' '.join([f.rel_path() for f in vl.depends_on if (f.name != vl.name)])
            include_dirs = list(set([os.path.dirname(f.rel_path()) for f in vl.depends_on if f.name.endswith("vh")]))
            while "" in include_dirs:
                include_dirs.remove("")
            include_dir_string = " -I".join(include_dirs)
            if include_dir_string:
                include_dir_string = ' -I'+include_dir_string
                self.writeln("VFLAGS_"+target_name+"="+include_dir_string)
            self.writeln(target_name+"_deps = "+dependencies_string)
            # self.write(target_name+': ')
            # self.write(vl.rel_path() + ' ')
            # self.writeln("$("+target_name+"_deps)")
            # self.write("\t\t$(VERILOG_COMP) -y"+vl.library)
            # if isinstance(vl, SVFile):
            #     self.write(" -sv ")
            # incdir = " "
            # incdir += " -I"
            # incdir += ' -I'.join(vl.include_dirs)
            # self.writeln(include_dir_string)
        sim_only_files = []
        for m in global_mod.mod_pool:
            for f in m.sim_only_files:
                sim_only_files.append(f.name)
        top_name = global_mod.top_module.syn_top
        top_name_syn_deps = []

        bit_targets = []
        for m in global_mod.mod_pool:
            bit_targets = bit_targets + m.bit_file_targets
        for bt in bit_targets:
            bt = bt.purename
            bt_syn_deps = []
            # This can perhaps be done faster (?)
            for vl in fileset.filter(VerilogFile):
                if vl.purename == bt:
                    for f in vl.depends_on:
                        if (f.name != vl.name and f.name not in sim_only_files):
                            bt_syn_deps.append(f)
            self.writeln(bt+'syn_deps = '+ ' '.join([f.rel_path() for f in bt_syn_deps]))
            if not os.path.exists("%s.ucf" % bt):
                logging.warning("The file %s.ucf doesn't exist!" % bt)
            self.writeln(bt+".bit:\t"+bt+".v $("+bt+"syn_deps) "+bt+".ucf")
            part=(global_mod.top_module.syn_device+'-'+
                  global_mod.top_module.syn_package+
                  global_mod.top_module.syn_grade)
            self.writeln("\tPART="+part+" $(SYNTH) "+bt+" $^")
            self.writeln("\tmv _xilinx/"+bt+".bit $@")

        self.writeln("clean:")
        self.writeln("\t\trm -f "+" ".join(target_list)+"\n\t\trm -rf _xilinx")

    def generate_vsim_makefile(self, fileset, top_module):
        from srcfile import VerilogFile, VHDLFile, SVFile
        make_preambule_p1 = """## variables #############################
PWD := $(shell pwd)

MODELSIM_INI_PATH := $(HDLMAKE_MODELSIM_PATH)"../"

VCOM_FLAGS := -quiet -modelsimini modelsim.ini
VSIM_FLAGS :=
VLOG_FLAGS := -quiet -modelsimini modelsim.ini """ + self.__get_rid_of_incdirs(top_module.vlog_opt) + """
"""
        make_preambule_p2 = Template("""## rules #################################
sim: sim_pre_cmd modelsim.ini $$(LIB_IND) $$(VERILOG_OBJ) $$(VHDL_OBJ)
$$(VERILOG_OBJ): $$(VHDL_OBJ)
$$(VHDL_OBJ): $$(LIB_IND) modelsim.ini

sim_pre_cmd:
\t\t${sim_pre_cmd}

sim_post_cmd: sim
\t\t${sim_post_cmd}

modelsim.ini: $$(MODELSIM_INI_PATH)/modelsim.ini
\t\tcp $$< .
clean:
\t\trm -rf ./modelsim.ini $$(LIBS)
.PHONY: clean sim_pre_cmd sim_post_cmd

""")
        #open the file and write the above preambule (part 1)
        self.initialize()
        self.write(make_preambule_p1)

        self.write("VERILOG_SRC := ")
        for vl in fileset.filter(VerilogFile):
            self.write(vl.rel_path() + " \\\n")
        self.write("\n")

        self.write("VERILOG_OBJ := ")
        for vl in fileset.filter(VerilogFile):
            #make a file compilation indicator (these .dat files are made even if
            #the compilation process fails) and add an ending according to file's
            #extension (.sv and .vhd files may have the same corename and this
            #causes a mess
            self.write(os.path.join(vl.library, vl.purename, "."+vl.purename+"_"+vl.extension()) + " \\\n")
        self.write('\n')

        libs = set(f.library for f in fileset)

        self.write("VHDL_SRC := ")
        for vhdl in fileset.filter(VHDLFile):
            self.write(vhdl.rel_path() + " \\\n")
        self.writeln()

        #list vhdl objects (_primary.dat files)
        self.write("VHDL_OBJ := ")
        for vhdl in fileset.filter(VHDLFile):
            #file compilation indicator (important: add _vhd ending)
            self.write(os.path.join(vhdl.library, vhdl.purename, "."+vhdl.purename+"_"+vhdl.extension()) + " \\\n")
        self.write('\n')

        self.write('LIBS := ')
        self.write(' '.join(libs))
        self.write('\n')
        #tell how to make libraries
        self.write('LIB_IND := ')
        self.write(' '.join([lib+"/."+lib for lib in libs]))
        self.write('\n')

        if top_module.sim_pre_cmd:
            sim_pre_cmd = top_module.sim_pre_cmd
        else:
            sim_pre_cmd = ''

        if top_module.sim_post_cmd:
            sim_post_cmd = top_module.sim_post_cmd
        else:
            sim_post_cmd = ''
        make_preambule_p2 = make_preambule_p2.substitute(sim_pre_cmd=sim_pre_cmd,
                                                         sim_post_cmd=sim_post_cmd)
        self.write(make_preambule_p2)

        for lib in libs:
            self.write(lib+"/."+lib+":\n")
            self.write(' '.join(["\t(vlib",  lib, "&&", "vmap", "-modelsimini modelsim.ini",
                       lib, "&&", "touch", lib+"/."+lib, ")"]))

            self.write(' '.join(["||", "rm -rf", lib, "\n"]))
            self.write('\n')

        #rules for all _primary.dat files for sv
        for vl in fileset.filter(VerilogFile):
            self.write(os.path.join(vl.library, vl.purename, '.'+vl.purename+"_"+vl.extension())+': ')
            self.write(vl.rel_path() + ' ')
            self.writeln(' '.join([f.rel_path() for f in vl.depends_on]))
            self.write("\t\tvlog -work "+vl.library)
            self.write(" $(VLOG_FLAGS) ")
            if isinstance(vl, SVFile):
                self.write(" -sv ")
            incdir = "+incdir+"
            incdir += '+'.join(vl.include_dirs)
            incdir += " "
            self.write(incdir)
            self.writeln(vl.vlog_opt+" $<")
            self.write("\t\t@mkdir -p $(dir $@)")
            self.writeln(" && touch $@ \n\n")
        self.write("\n")

        #list rules for all _primary.dat files for vhdl
        for vhdl in fileset.filter(VHDLFile):
            lib = vhdl.library
            purename = vhdl.purename
            #each .dat depends on corresponding .vhd file
            self.write(os.path.join(lib, purename, "."+purename+"_" + vhdl.extension()) + ": " + vhdl.rel_path())
            for dep_file in vhdl.depends_on:
                name = dep_file.purename
                self.write(" \\\n" + os.path.join(dep_file.library, name, ".%s_vhd" % name))
            self.writeln()
            self.writeln(' '.join(["\t\tvcom $(VCOM_FLAGS)", vhdl.vcom_opt, "-work", lib, "$< "]))
            self.writeln("\t\t@mkdir -p $(dir $@) && touch $@\n")
            self.writeln()

# Modification here
    def generate_isim_makefile(self, fileset, top_module):
        from srcfile import VerilogFile, VHDLFile
        from tools.ise import XilinxsiminiReader
        make_preambule_p1 = """## variables #############################
PWD := $(shell pwd)
TOP_MODULE := """ + top_module.top_module + """
FUSE_OUTPUT ?= isim_proj

XILINX_INI_PATH := """ + XilinxsiminiReader.xilinxsim_ini_dir() + """

VHPCOMP_FLAGS := -intstyle default -incremental -initfile xilinxsim.ini
ISIM_FLAGS :=
VLOGCOMP_FLAGS := -intstyle default -incremental -initfile xilinxsim.ini """ + self.__get_rid_of_incdirs(top_module.vlog_opt) + """
"""
        make_preambule_p2 = """## rules #################################
sim: xilinxsim.ini $(LIB_IND) $(VERILOG_OBJ) $(VHDL_OBJ)
$(VERILOG_OBJ): $(LIB_IND) xilinxsim.ini
$(VHDL_OBJ): $(LIB_IND) xilinxsim.ini

xilinxsim.ini: $(XILINX_INI_PATH)/xilinxsim.ini
\t\tcp $< .
fuse:
\t\tfuse work.$(TOP_MODULE) -intstyle ise -incremental -o $(FUSE_OUTPUT)
clean:
\t\trm -rf ./xilinxsim.ini $(LIBS) fuse.xmsgs fuse.log fuseRelaunch.cmd isim isim.log \
isim.wdb
.PHONY: clean

"""
        #open the file and write the above preambule (part 1)
        self.initialize()
        self.write(make_preambule_p1)

        self.write("VERILOG_SRC := ")
        for vl in fileset.filter(VerilogFile):
            self.write(vl.rel_path() + " \\\n")
        self.write("\n")

        self.write("VERILOG_OBJ := ")
        for vl in fileset.filter(VerilogFile):
            #make a file compilation indicator (these .dat files are made even if
            #the compilation process fails) and add an ending according to file's
            #extension (.sv and .vhd files may have the same corename and this
            #causes a mess
            self.write(os.path.join(vl.library, vl.purename, "."+vl.purename+"_"+vl.extension()) + " \\\n")
        self.write('\n')

        libs = set(f.library for f in fileset)

        self.write("VHDL_SRC := ")
        for vhdl in fileset.filter(VHDLFile):
            self.write(vhdl.rel_path() + " \\\n")
        self.writeln()

        #list vhdl objects (_primary.dat files)
        self.write("VHDL_OBJ := ")
        for vhdl in fileset.filter(VHDLFile):
            #file compilation indicator (important: add _vhd ending)
            self.write(os.path.join(vhdl.library, vhdl.purename, "."+vhdl.purename+"_"+vhdl.extension()) + " \\\n")
        self.write('\n')

        self.write('LIBS := ')
        self.write(' '.join(libs))
        self.write('\n')
        #tell how to make libraries
        self.write('LIB_IND := ')
        self.write(' '.join([lib+"/."+lib for lib in libs]))
        self.write('\n')
        self.write(make_preambule_p2)

        # ISim does not have a vmap command to insert additional libraries in
        #.ini file.
        for lib in libs:
            self.write(lib+"/."+lib+":\n")
            self.write(' '.join(["\t(mkdir", lib, "&&", "touch", lib+"/."+lib+" "]))
            #self.write(' '.join(["&&", "echo", "\""+lib+"="+lib+"/."+lib+"\" ", ">>", "xilinxsim.ini) "]))
            self.write(' '.join(["&&", "echo", "\""+lib+"="+lib+"\" ", ">>", "xilinxsim.ini) "]))
            self.write(' '.join(["||", "rm -rf", lib, "\n"]))
            self.write('\n')

            # Modify xilinxsim.ini file by including the extra local libraries
            #self.write(' '.join(["\t(echo """, lib+"="+lib+"/."+lib, ">>", "${XILINX_INI_PATH}/xilinxsim.ini"]))

        #rules for all _primary.dat files for sv
        #incdir = ""
        objs = []
        for vl in fileset.filter(VerilogFile):
            comp_obj = os.path.join(vl.library, vl.purename)
            objs.append(comp_obj)
            #self.write(os.path.join(vl.library, vl.purename, '.'+vl.purename+"_"+vl.extension())+': ')
            #self.writeln(".PHONY: " + os.path.join(comp_obj, '.'+vl.purename+"_"+vl.extension()))
            self.write(os.path.join(comp_obj, '.'+vl.purename+"_"+vl.extension())+': ')
            self.write(vl.rel_path() + ' ')
            self.writeln(' '.join([fname.rel_path() for fname in vl.depends_on]))
            self.write("\t\tvlogcomp -work "+vl.library+"=./"+vl.library)
            self.write(" $(VLOGCOMP_FLAGS) ")
            #if isinstance(vl, SVFile):
            #    self.write(" -sv ")
            #incdir = "-i "
            #incdir += " -i ".join(vl.include_dirs)
            #incdir += " "
            self.write(" -i ".join(vl.include_dirs) + " ")
            self.writeln(vl.vlog_opt+" $<")
            self.write("\t\t@mkdir -p $(dir $@)")
            self.writeln(" && touch $@ \n\n")
        self.write("\n")

        #list rules for all _primary.dat files for vhdl
        for vhdl in fileset.filter(VHDLFile):
            lib = vhdl.library
            purename = vhdl.purename
            comp_obj = os.path.join(lib, purename)
            objs.append(comp_obj)
            #each .dat depends on corresponding .vhd file and its dependencies
            #self.write(os.path.join(lib, purename, "."+purename+"_"+ vhdl.extension()) + ": "+ vhdl.rel_path()+" " + os.path.join(lib, purename, "."+purename) + '\n')
            #self.writeln(".PHONY: " + os.path.join(comp_obj, "."+purename+"_"+ vhdl.extension()))
            self.write(os.path.join(comp_obj, "."+purename+"_" + vhdl.extension()) + ": " + vhdl.rel_path()+" " + os.path.join(lib, purename, "."+purename) + '\n')
            self.writeln(' '.join(["\t\tvhpcomp $(VHPCOMP_FLAGS)", vhdl.vcom_opt, "-work", lib+"=./"+lib, "$< "]))
            self.writeln("\t\t@mkdir -p $(dir $@) && touch $@\n")
            self.writeln()
            # dependency meta-target. This rule just list the dependencies of the above file
            #if len(vhdl.depends_on) != 0:
            #self.writeln(".PHONY: " + os.path.join(lib, purename, "."+purename))
            # Touch the dependency file as well. In this way, "make" will recompile only what is needed (out of date)
            #if len(vhdl.depends_on) != 0:
            self.write(os.path.join(lib, purename, "."+purename) + ":")
            for dep_file in vhdl.depends_on:
                name = dep_file.purename
                self.write(" \\\n" + os.path.join(dep_file.library, name, "."+name + "_" + vhdl.extension()))
            self.write('\n')
            self.writeln("\t\t@mkdir -p $(dir $@) && touch $@\n")

    def __get_rid_of_incdirs(self, vlog_opt):
        vlog_opt_vsim = self.__get_rid_of_vsim_incdirs(vlog_opt)
        return self.__get_rid_of_isim_incdirs(vlog_opt_vsim)

    def __get_rid_of_vsim_incdirs(self, vlog_opt):
        vlog_opt = self.__emit_string(vlog_opt)
        vlogs = vlog_opt.split(' ')
        ret = []
        for v in vlogs:
            if not v.startswith("+incdir+"):
                ret.append(v)
        return ' '.join(ret)

    # FIX. Make it more robust
    def __get_rid_of_isim_incdirs(self, vlog_opt):
        vlog_opt = self.__emit_string(vlog_opt)
        vlogs = vlog_opt.split(' ')
        ret = []
        skip = False
        for v in vlogs:
            if skip:
                skip = False
                continue

            if not v.startswith("-i"):
                ret.append(v)
            else:
                skip = True
        return ' '.join(ret)

    def __emit_string(self, s):
        if not s:
            return ""
        else:
            return s

    def __modelsim_ini_path(self):
        vsim_path = os.popen("which vsim").read().strip()
        bin_path = os.path.dirname(vsim_path)
        return os.path.abspath(bin_path+"/../")
