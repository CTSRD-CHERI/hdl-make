action = "simulation"
sim_tool = "modelsim"
sim_top = "counter_tb"

sim_post_cmd = "vsim -do ../vsim.do -i counter_tb"

modules = {
  "local" : [ "../../../testbench/counter_tb/vhdl" ],
}
