#!/usr/bin/python
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

from .action import Action
from hdlmake.util import path

import logging

class Tree(Action):
    def run(self):
        try:
            import networkx as nx
        except Exception as e:
            logging.error(e)
            quit()
        unfetched_modules = False
        files_str = []
        hierarchy = nx.DiGraph()
        color_index = 0

        if self.options.solved:
            logging.warning("This is the solved tree")
        else:
            for m in self.modules_pool:
                if not m.isfetched:
                    unfetched_modules = True
                else:
                    if m.parent: 
                        hierarchy.add_node(path.relpath(m.path))
                        hierarchy.add_edge(path.relpath(m.parent.path), path.relpath(m.path))
                    else:
                        hierarchy.add_node(path.relpath(m.path))
                        top_id = path.relpath(m.path)
                    if self.options.withfiles:
                        if len(m.files):
                            for f in m.files:
                                hierarchy.add_edge(path.relpath(m.path), path.relpath(f.path))
                color_index += 1

        if unfetched_modules: logging.warning("Some of the modules have not been fetched!")

        # Define the program used to write the graphviz:
        # Program should be one of: 
        #     twopi, gvcolor, wc, ccomps, tred, sccmap, fdp, 
        #     circo, neato, acyclic, nop, gvpr, dot, sfdp.
        if self.options.graphviz:
            try:
                import matplotlib.pyplot as plt
            except Exception as e:
                logging.error(e)
                quit()
            pos=nx.graphviz_layout(hierarchy, prog=self.options.graphviz, root=top_id)
            nx.draw(hierarchy, pos,
                with_labels=True,
                alpha=0.5,
                node_size=100)
            plt.savefig("hierarchy.png")
            plt.show()


        if self.options.web:
            try:
                import json
                from networkx.readwrite import json_graph
            except Exception as e:
                logging.error(e)
                quit()
            data = json_graph.tree_data(hierarchy, root=top_id)
            s = json.dumps(data)
            json_file = open("hierarchy.json", "w")
            json_file.write(s)
            json_file.close()



